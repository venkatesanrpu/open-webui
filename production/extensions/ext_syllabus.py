"""
ext_syllabus.py — Syllabus content delivery for the CSIR AI platform.

Routes (all mounted under /api/ext/syllabus by main.py injection):
  GET /prompts/{function_name}  — prompt template with per-exam override support
  GET /index                    — full recursive syllabus tree (all folders)
  GET /trial-index              — tree filtered to always_active plan folders (no auth)
  GET /meta                     — all syllabus.json files (for CategorizedHistory)

The /index response now includes a '_meta' key at every node that has a
metadata.json file (course-level folders).  The frontend reads _meta.folder_key
to resolve entitlement checks without making an additional API call.

The /trial-index endpoint is intentionally unauthenticated — Trial content is
visible to all visitors.  It reads content_manifest.json + ext_plans to determine
which folder_keys are always_active, then returns only those subtrees.
"""

import json
import logging
import os
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import create_engine, text

# ── Audit helper (best-effort) ────────────────────────────────────────────────
try:
    from open_webui.routers import ext_authz
except Exception:
    try:
        import ext_authz
    except Exception:
        ext_authz = None


def _audit(**kwargs) -> None:
    if ext_authz is None:
        return
    try:
        ext_authz.log_event(**kwargs)
    except Exception:
        pass


router = APIRouter()
log = logging.getLogger("ext_syllabus")

SYLLABUS_DIR = os.getenv("SYLLABUS_DIR", "/app/data/syllabus")
PROMPTS_DIR  = os.getenv("PROMPTS_DIR",  "/app/data/prompts")

_SAFE_ID = re.compile(r"^[A-Za-z0-9_]+$")
_SYLLABUS_CACHE_CONTROL = "public, max-age=60"

# ── Database setup (needed by trial-index to query always_active plans) ───────
_DATABASE_URL = os.getenv("DATABASE_URL", "")
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)

_db_engine = None
if _DATABASE_URL:
    try:
        _db_engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
    except Exception as exc:
        log.error("ext_syllabus: failed to create DB engine: %s", exc)

# ── Hardcoded minimal fallbacks ───────────────────────────────────────────────
_FALLBACK_PROMPTS = {
    "ask_agent": (
        "Prompt template 'ask_agent' is unavailable on the server.\n"
        "Subject: {SUBJECT}\nTopic: {TOPIC}\nFocus: {CONCEPT}\nContext: {CLARIFICATION}\n"
        "Please provide study notes using your best general guidance."
    ),
    "mcq_widget": (
        "Prompt template 'mcq_widget' is unavailable on the server.\n"
        "Subject: {SUBJECT}\nTopic: {TOPIC}\nFocus: {CONCEPT}\n"
        "Level: {LEVEL}\nQuestions: {NUM_QUESTIONS}\n"
        "Please generate MCQs using your best general guidance."
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# Content integrity validation
# ══════════════════════════════════════════════════════════════════════════════

_content_validated = False


def _validate_content_integrity() -> None:
    """
    Validates content_manifest.json against the physical syllabus tree.

    Called once per process (guarded by _content_validated flag) from the
    first request to /index or /trial-index.

    Soft-fail policy:
      - Missing manifest  → WARNING  (operators may not have run generate_manifest.py yet)
      - Missing paths     → ERROR    (content is referenced but absent)
      - Duplicate keys    → ERROR    (would cause entitlement ambiguity)
      - metadata mismatch → ERROR    (folder_key in manifest ≠ metadata.json)
    The server continues running in all cases; errors are surfaced through logs,
    not HTTP 500s, so a partially broken content tree does not bring the whole
    app down.
    """
    global _content_validated
    if _content_validated:
        return
    _content_validated = True

    base = Path(SYLLABUS_DIR)
    manifest_path = base / "content_manifest.json"

    if not manifest_path.is_file():
        log.warning(
            "[ext_syllabus] content_manifest.json not found at %s — "
            "run scripts/generate_manifest.py to create it.",
            SYLLABUS_DIR,
        )
        return

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.error("[ext_syllabus] content_manifest.json is invalid JSON: %s", exc)
        return

    seen_keys: set[str] = set()
    errors: list[str] = []

    for folder_key, rel_path in manifest.get("folders", {}).items():
        if folder_key in seen_keys:
            errors.append(f"duplicate folder_key '{folder_key}'")
        seen_keys.add(folder_key)

        full_path = base / rel_path
        if not full_path.is_dir():
            errors.append(f"physical path missing for '{folder_key}': {rel_path}")
            continue

        meta_file = full_path / "metadata.json"
        if not meta_file.is_file():
            errors.append(f"metadata.json missing in {rel_path}")
        else:
            try:
                meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
                actual_key = meta_data.get("folder_key", "")
                if actual_key != folder_key:
                    errors.append(
                        f"folder_key mismatch: manifest='{folder_key}' "
                        f"but metadata.json says '{actual_key}' in {rel_path}"
                    )
            except Exception as exc:
                errors.append(f"metadata.json invalid in {rel_path}: {exc}")

    if errors:
        for err in errors:
            log.error("[ext_syllabus] Content integrity error: %s", err)
    else:
        log.info(
            "[ext_syllabus] Content integrity OK: %d folder(s) validated.",
            len(seen_keys),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Path helpers
# ══════════════════════════════════════════════════════════════════════════════

def _is_safe_id(name: str) -> bool:
    return bool(name) and bool(_SAFE_ID.match(name))


def _resolve_within(base: Path, *parts: str) -> "Path | None":
    """
    Resolve base/<parts> and return the path only if it stays under base
    after symlink/.. normalisation (path-traversal guard).
    """
    try:
        base_resolved = base.resolve()
        candidate = (base / Path(*parts)).resolve()
    except Exception:
        return None
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        return None
    return candidate


# ══════════════════════════════════════════════════════════════════════════════
# HTML file parser
# ══════════════════════════════════════════════════════════════════════════════

def parse_html_file(file_path: str) -> dict:
    """
    Extracts <a data-*> anchor metadata from a lesson HTML file.
    Returns { filename, metadata, links } or { filename, error }.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except Exception as exc:
        return {"filename": os.path.basename(file_path), "error": str(exc)}

    soup = BeautifulSoup(content, "html.parser")
    links: list[dict] = []
    metadata: dict = {}

    for idx, a in enumerate(soup.find_all("a")):
        data_attrs = {
            k.replace("data-", ""): v
            for k, v in a.attrs.items()
            if k.startswith("data-")
        }

        if not metadata and data_attrs:
            metadata = {
                "lesson":       data_attrs.get("lesson", ""),
                "concept":      data_attrs.get("core", ""),
                "clarification": data_attrs.get("agent-text", ""),
            }
        elif metadata and data_attrs:
            for src_key, meta_key in (
                ("lesson", "lesson"),
                ("core", "concept"),
                ("agent-text", "clarification"),
            ):
                if src_key in data_attrs and data_attrs[src_key] != metadata.get(meta_key, ""):
                    log.warning(
                        "[ext_syllabus] %s: anchor #%d data-%s=%r disagrees with "
                        "first-link metadata %r",
                        os.path.basename(file_path), idx, src_key,
                        data_attrs[src_key], metadata.get(meta_key, ""),
                    )

        if data_attrs.get("function") == "mcq_widget":
            missing = [k for k in ("level", "number") if not data_attrs.get(k)]
            if missing:
                log.warning(
                    "[ext_syllabus] %s: anchor #%d mcq_widget missing data-%s",
                    os.path.basename(file_path), idx, ", data-".join(missing),
                )

        links.append({"label": a.text.strip(), "data": data_attrs})

    return {"filename": os.path.basename(file_path), "metadata": metadata, "links": links}


# ══════════════════════════════════════════════════════════════════════════════
# Tree builder — module-level so both /index and /trial-index can share it
# ══════════════════════════════════════════════════════════════════════════════

def build_tree(current_path: str) -> dict:
    """
    Recursively scan current_path and return a nested dict tree:
      {
        "_meta":  { ...metadata.json contents... },   ← present when metadata.json exists
        "folder1": { <subtree> },
        "folder2": { <subtree> },
        "_files": [ { filename, metadata, links }, ... ]
      }

    The '_meta' key is injected at any level that has a metadata.json file
    (conventionally the course-level folder, e.g. CHEM100/).  Frontend code
    reads _meta.folder_key to resolve entitlement checks without extra API calls.

    The '_files' and '_meta' key names are prefixed with '_' to distinguish them
    from folder children (the same convention used by the existing '_files' key).
    """
    tree: dict = {}

    # Inject metadata.json if present at this directory level.
    meta_file = os.path.join(current_path, "metadata.json")
    if os.path.isfile(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as fh:
                tree["_meta"] = json.load(fh)
        except Exception as exc:
            log.warning(
                "[ext_syllabus] Failed to read metadata.json at %s: %s",
                current_path, exc,
            )

    # Subdirectories — sorted so ordering is deterministic across OSes.
    dirs = sorted(
        d for d in os.listdir(current_path)
        if os.path.isdir(os.path.join(current_path, d))
    )
    for d in dirs:
        subtree = build_tree(os.path.join(current_path, d))
        # Include non-empty subtrees AND leaf dirs that contain HTML files.
        if subtree or any(
            f.endswith(".html")
            for f in os.listdir(os.path.join(current_path, d))
        ):
            tree[d] = subtree

    # HTML files at this level — core_ first, then related_, then others.
    def _file_sort_key(fname: str) -> tuple:
        if fname.startswith("core_"):
            return (0, fname)
        if fname.startswith("related_"):
            return (1, fname)
        return (2, fname)

    html_files = sorted(
        (
            f for f in os.listdir(current_path)
            if os.path.isfile(os.path.join(current_path, f)) and f.endswith(".html")
        ),
        key=_file_sort_key,
    )
    if html_files:
        tree["_files"] = [
            parse_html_file(os.path.join(current_path, f)) for f in html_files
        ]

    return tree


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/prompts/{function_name}")
async def get_prompt_template(function_name: str, exam: str = ""):
    """
    Returns a prompt template for function_name.

    Resolution order:
      1. Per-exam override: SYLLABUS_DIR/{exam}/prompts/{function_name}.txt
      2. Global default:    PROMPTS_DIR/{function_name}.txt
      3. Hardcoded minimal fallback (signals 'template missing')
    """
    started = time.monotonic()
    if not _is_safe_id(function_name):
        raise HTTPException(status_code=400, detail="Invalid function_name")

    headers = {"Cache-Control": _SYLLABUS_CACHE_CONTROL}

    def _emit(status: str) -> None:
        _audit(
            user_id="anonymous",
            endpoint_type="prompt_template_fetched",
            request_duration_ms=int((time.monotonic() - started) * 1000),
            exam=exam or None,
            function=function_name,
            status=status,
        )

    if exam:
        if not _is_safe_id(exam):
            raise HTTPException(status_code=400, detail="Invalid exam identifier")
        exam_prompt = _resolve_within(
            Path(SYLLABUS_DIR), exam, "prompts", f"{function_name}.txt"
        )
        if exam_prompt and exam_prompt.is_file():
            _emit("hit_exam")
            return PlainTextResponse(
                exam_prompt.read_text(encoding="utf-8"), headers=headers
            )

    global_prompt = _resolve_within(Path(PROMPTS_DIR), f"{function_name}.txt")
    if global_prompt and global_prompt.is_file():
        _emit("hit_global")
        return PlainTextResponse(
            global_prompt.read_text(encoding="utf-8"), headers=headers
        )

    fallback = _FALLBACK_PROMPTS.get(function_name)
    if fallback:
        _emit("fallback")
        return PlainTextResponse(fallback, headers=headers)

    _emit("missing")
    return PlainTextResponse(
        f"No prompt template found for '{function_name}'.",
        status_code=404,
    )


@router.get("/index")
async def get_syllabus_index():
    """
    Recursively scans the syllabus directory and returns the full content tree.

    Each node that has a metadata.json will include a '_meta' key so the
    frontend can resolve folder_key → entitlement without additional API calls.
    """
    _validate_content_integrity()

    base_path = Path(SYLLABUS_DIR)
    if not base_path.exists():
        return JSONResponse({"error": "Data directory not found."})

    return JSONResponse(
        build_tree(str(base_path)),
        headers={"Cache-Control": _SYLLABUS_CACHE_CONTROL},
    )


@router.get("/trial-index")
async def get_trial_index():
    """
    Returns the syllabus tree filtered to folders belonging to always_active
    plans.  No authentication required — Trial content is freely accessible.

    Resolution:
      1. Read content_manifest.json → folder_key → relative path map
      2. Query ext_plans WHERE always_active = true → get folder_keys JSONB array
      3. For each qualifying folder_key, build the subtree and nest it under the
         original exam/course hierarchy so the sidebar renders correctly.

    Falls back to an empty tree (not an error) when:
      - content_manifest.json is missing
      - Database is unavailable
      - No always_active plans exist yet
    """
    _validate_content_integrity()

    base_path = Path(SYLLABUS_DIR)
    if not base_path.exists():
        return JSONResponse({})

    # Load manifest.
    manifest_path = base_path / "content_manifest.json"
    if not manifest_path.is_file():
        log.warning(
            "[ext_syllabus] trial-index: content_manifest.json not found — "
            "run scripts/generate_manifest.py"
        )
        return JSONResponse({}, headers={"Cache-Control": _SYLLABUS_CACHE_CONTROL})

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        folders_map: dict[str, str] = manifest.get("folders", {})
    except Exception as exc:
        log.error("[ext_syllabus] trial-index: cannot parse manifest: %s", exc)
        return JSONResponse({})

    # Determine which folder_keys belong to always_active plans.
    always_active_keys: set[str] = set()
    if _db_engine:
        try:
            with _db_engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT folder_keys FROM ext_plans WHERE always_active = true")
                ).fetchall()
            for row in rows:
                raw = row[0]
                if isinstance(raw, list):
                    always_active_keys.update(raw)
                else:
                    try:
                        always_active_keys.update(json.loads(raw or "[]"))
                    except Exception:
                        pass
        except Exception as exc:
            log.error("[ext_syllabus] trial-index: DB query failed: %s", exc)
    else:
        log.warning("[ext_syllabus] trial-index: DB unavailable, returning empty tree")

    if not always_active_keys:
        return JSONResponse({}, headers={"Cache-Control": _SYLLABUS_CACHE_CONTROL})

    # Build filtered tree preserving the full exam/course hierarchy so the
    # sidebar SyllabusNode renders the same nested structure as /index.
    tree: dict = {}
    for folder_key in sorted(always_active_keys):
        rel_path = folders_map.get(folder_key)
        if not rel_path:
            log.warning(
                "[ext_syllabus] trial-index: folder_key '%s' not in manifest",
                folder_key,
            )
            continue

        phys_path = base_path / rel_path
        if not phys_path.is_dir():
            log.warning(
                "[ext_syllabus] trial-index: path '%s' not found for '%s'",
                rel_path, folder_key,
            )
            continue

        # Navigate / create the nesting levels in tree to match the physical path.
        # e.g. rel_path = "Trial/trial_chemistry" → tree["Trial"]["trial_chemistry"]
        parts = rel_path.replace("\\", "/").split("/")
        cursor = tree
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        last_part = parts[-1]
        cursor[last_part] = build_tree(str(phys_path))

    return JSONResponse(tree, headers={"Cache-Control": _SYLLABUS_CACHE_CONTROL})


@router.get("/meta")
async def get_syllabus_meta():
    """
    Auto-discovers all syllabus.json files under SYLLABUS_DIR.
    Used by CategorizedHistory to build the history filter tree.
    """
    base_path = Path(SYLLABUS_DIR)
    if not base_path.exists():
        return JSONResponse([])

    result = []
    for syllabus_file in base_path.rglob("syllabus.json"):
        try:
            with open(syllabus_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            rel_path = syllabus_file.relative_to(base_path)
            parts = rel_path.parts[:-1]

            data["_exam_folder"] = (
                parts[0].replace("_", " ") if len(parts) > 0 else "General"
            )
            data["_course_folder"] = parts[1] if len(parts) > 1 else ""
            data["_path"] = "/".join(parts)

            result.append(data)
        except Exception as exc:
            result.append({"error": str(exc), "path": str(syllabus_file)})

    return JSONResponse(result, headers={"Cache-Control": _SYLLABUS_CACHE_CONTROL})

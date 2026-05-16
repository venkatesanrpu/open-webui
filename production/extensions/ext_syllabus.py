import os
import re
import json
import logging
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse, JSONResponse
from pathlib import Path
from bs4 import BeautifulSoup

router = APIRouter()
log = logging.getLogger("ext_syllabus")

SYLLABUS_DIR = os.getenv("SYLLABUS_DIR", "/app/data/syllabus")
PROMPTS_DIR = os.getenv("PROMPTS_DIR", "/app/data/prompts")

# Identifiers that participate in filesystem path construction must be
# whitespace-free, dot-free, slash-free and contain no parent-directory
# components. The pattern below mirrors valid existing identifiers such as
# `csir_physical_sciences` and `ask_agent` while rejecting any traversal
# attempt (`..`, `/`, NUL bytes, etc.).
_SAFE_ID = re.compile(r"^[A-Za-z0-9_]+$")

# Modest cache window for static-ish syllabus assets. Short enough that
# authoring iterations are visible quickly; long enough to spare the disk on
# bulk sidebar renders. Public is safe — content is not user-scoped.
_SYLLABUS_CACHE_CONTROL = "public, max-age=60"


def _is_safe_id(name: str) -> bool:
    return bool(name) and bool(_SAFE_ID.match(name))


def _resolve_within(base: Path, *parts: str) -> Path | None:
    """
    Resolve ``base/<parts...>`` and return the resolved path only if it stays
    under ``base`` after symlink/`..` normalization. Returns None otherwise.
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


# ── Hardcoded fallbacks ──
#
# These are minimal "template missing" messages, NOT rich prompt clones. The
# review flagged the prior rich fallbacks as a drift hazard: if the on-disk
# template is edited but the fallback is not, the two diverge silently and a
# missing-file scenario produces a different model behavior than the intended
# template. Keeping fallbacks deliberately minimal makes the missing-template
# state diagnosable in the chat output instead of disguising it.
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


@router.get("/prompts/{function_name}")
async def get_prompt_template(function_name: str, exam: str = ""):
    """
    Returns a prompt template for the given function_name.

    Resolution order:
    1. Per-exam override: SYLLABUS_DIR/{exam}/prompts/{function_name}.txt
    2. Global default:   PROMPTS_DIR/{function_name}.txt
    3. Hardcoded minimal fallback (signals "template missing")

    Both `exam` and `function_name` are validated against an allow-list and
    the resolved path is asserted to stay under its respective base directory
    to prevent path traversal (e.g. `../../etc/passwd`).
    """
    if not _is_safe_id(function_name):
        raise HTTPException(status_code=400, detail="Invalid function_name")

    headers = {"Cache-Control": _SYLLABUS_CACHE_CONTROL}

    # 1. Per-exam override
    if exam:
        if not _is_safe_id(exam):
            raise HTTPException(status_code=400, detail="Invalid exam identifier")
        exam_prompt = _resolve_within(
            Path(SYLLABUS_DIR), exam, "prompts", f"{function_name}.txt"
        )
        if exam_prompt and exam_prompt.is_file():
            return PlainTextResponse(
                exam_prompt.read_text(encoding="utf-8"), headers=headers
            )

    # 2. Global default
    global_prompt = _resolve_within(Path(PROMPTS_DIR), f"{function_name}.txt")
    if global_prompt and global_prompt.is_file():
        return PlainTextResponse(
            global_prompt.read_text(encoding="utf-8"), headers=headers
        )

    # 3. Hardcoded fallback
    fallback = _FALLBACK_PROMPTS.get(function_name)
    if fallback:
        return PlainTextResponse(fallback, headers=headers)

    return PlainTextResponse(
        f"No prompt template found for '{function_name}'.",
        status_code=404,
    )


def parse_html_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {"filename": os.path.basename(file_path), "error": str(e)}

    soup = BeautifulSoup(content, 'html.parser')
    links = []
    metadata = {}

    a_tags = soup.find_all('a')
    for idx, a in enumerate(a_tags):
        # Extract data attributes
        data_attrs = {k.replace('data-', ''): v for k, v in a.attrs.items() if k.startswith('data-')}

        # Populate metadata once from the first link (as they share lesson/core/agent-text)
        if not metadata and data_attrs:
            metadata = {
                "lesson": data_attrs.get("lesson", ""),
                "concept": data_attrs.get("core", ""),
                "clarification": data_attrs.get("agent-text", "")
            }
        elif metadata and data_attrs:
            # LOW-8: Warn if a subsequent anchor disagrees with the first
            # anchor's lesson / core / agent-text. Authors occasionally
            # duplicate anchors with slightly drifted metadata; we want to
            # surface that during dev without breaking the parse.
            for src_key, meta_key in (
                ("lesson", "lesson"),
                ("core", "concept"),
                ("agent-text", "clarification"),
            ):
                if src_key in data_attrs and data_attrs[src_key] != metadata.get(meta_key, ""):
                    log.warning(
                        "[ext_syllabus] %s: anchor #%d data-%s=%r disagrees with first-link metadata %r",
                        os.path.basename(file_path), idx, src_key,
                        data_attrs[src_key], metadata.get(meta_key, ""),
                    )

        # LOW-9: For mcq_widget anchors, data-level and data-number are part
        # of the Smart Router cache identity; missing them collapses distinct
        # difficulty/quantity variants into the same key. Warn but accept.
        if data_attrs.get("function") == "mcq_widget":
            missing = [k for k in ("level", "number") if not data_attrs.get(k)]
            if missing:
                log.warning(
                    "[ext_syllabus] %s: anchor #%d mcq_widget missing required data-%s",
                    os.path.basename(file_path), idx, ", data-".join(missing),
                )

        links.append({
            "label": a.text.strip(),
            "data": data_attrs
        })

    return {
        "filename": os.path.basename(file_path),
        "metadata": metadata,
        "links": links
    }

@router.get("/index")
async def get_syllabus_index():
    """
    Recursively scans the syllabus directory, parses HTML files, and builds a strict-sorted JSON tree.
    """
    base_path = Path(SYLLABUS_DIR)
    if not base_path.exists():
        return JSONResponse({"error": "Data directory not found."})

    def build_tree(current_path):
        tree = {}

        # Get directories and sort them alphabetically
        dirs = [d for d in os.listdir(current_path) if os.path.isdir(os.path.join(current_path, d))]
        dirs.sort() # Enforces 01_unit, 02_unit order

        for d in dirs:
            subtree = build_tree(os.path.join(current_path, d))
            # Only add to tree if it's not empty or if it's a leaf
            if subtree or any(f.endswith('.html') for f in os.listdir(os.path.join(current_path, d))):
                tree[d] = subtree

        # Get HTML files
        files = [f for f in os.listdir(current_path) if os.path.isfile(os.path.join(current_path, f)) and f.endswith('.html')]

        # Sort files: core_ first, then related_, then others alphabetically
        def file_sort_key(f):
            if f.startswith('core_'):
                return (0, f)
            elif f.startswith('related_'):
                return (1, f)
            return (2, f)

        files.sort(key=file_sort_key)

        if files:
            parsed_files = []
            for f in files:
                parsed = parse_html_file(os.path.join(current_path, f))
                parsed_files.append(parsed)
            tree["_files"] = parsed_files

        return tree

    return JSONResponse(
        build_tree(base_path),
        headers={"Cache-Control": _SYLLABUS_CACHE_CONTROL},
    )


@router.get("/meta")
async def get_syllabus_meta():
    """
    Auto-discovers all syllabus.json files under SYLLABUS_DIR.
    Infers exam/course context from the directory path.
    Returns an array of all discovered syllabi for the History filter tree.

    Expected structure:
      SYLLABUS_DIR/
        CSIR_Physical_Sciences/   ← top-level folder (exam context)
          phys100/                ← course folder
            syllabus.json         ← discovered here
            unit_01/
              unit_1A/
                core_xxx.html
    """
    base_path = Path(SYLLABUS_DIR)
    if not base_path.exists():
        return JSONResponse([])

    result = []
    for syllabus_file in base_path.rglob("syllabus.json"):
        try:
            with open(syllabus_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Infer context from directory path
            # e.g., CSIR_Physical_Sciences/phys100/syllabus.json
            rel_path = syllabus_file.relative_to(base_path)
            parts = rel_path.parts[:-1]  # Remove 'syllabus.json' itself

            # First part = exam/program folder, rest = course context
            data["_exam_folder"] = parts[0].replace('_', ' ') if len(parts) > 0 else "General"
            data["_course_folder"] = parts[1] if len(parts) > 1 else ""
            data["_path"] = "/".join(parts)

            result.append(data)
        except Exception as e:
            result.append({
                "error": str(e),
                "path": str(syllabus_file)
            })

    return JSONResponse(result, headers={"Cache-Control": _SYLLABUS_CACHE_CONTROL})

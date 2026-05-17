"""
ext_entitlements.py — User entitlement management for the CSIR AI platform.

Routes (all mounted under /api/ext by main.py injection):
  GET  /entitlements/{user_id}   — full entitlement list; lazy-provisions trial
  GET  /access/check             — single folder_key access check for a given action
  POST /entitlements/provision   — payment webhook stub (Phase 3 / Razorpay)

Design contract:
  - History viewing and cache hits are NEVER gated (action != 'generate').
  - Only new-generation actions are gated.
  - always_active plans (Trial) are auto-provisioned on first call per user.
  - The frontend calls /access/check before calling generateNotes() and renders
    the result as locked/unlocked button state.  The backend is the only source
    of truth; the frontend never decides access on its own.
  - Audit failures never surface as 5xx errors.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text

# ── Open WebUI verified-user dependency (best-effort import) ──────────────────
try:
    from open_webui.utils.auth import get_verified_user as _get_verified_user
    from fastapi import Depends
except Exception:
    _get_verified_user = None
    try:
        from fastapi import Depends
    except Exception:
        Depends = None

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


# ── Auth dependency helpers (mirrors ext_router.py pattern) ──────────────────

def _user_dep():
    if _get_verified_user is not None and Depends is not None:
        return Depends(_get_verified_user)

    async def _noop():
        return None

    return Depends(_noop) if Depends else None


def _resolve_user_id(verified_user, fallback: str = "") -> str:
    if verified_user is not None:
        uid = getattr(verified_user, "id", None)
        if uid:
            return str(uid)
    return fallback or ""


# ── Database setup (mirrors ext_router.py pattern) ───────────────────────────

log = logging.getLogger("ext_entitlements")

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    except Exception as exc:
        log.error("ext_entitlements: failed to create DB engine: %s", exc)

SYLLABUS_DIR = os.getenv("SYLLABUS_DIR", "/app/data/syllabus")

router = APIRouter()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_manifest() -> dict:
    """Load content_manifest.json. Returns empty dict on any error."""
    manifest_path = Path(SYLLABUS_DIR) / "content_manifest.json"
    if manifest_path.is_file():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("ext_entitlements: could not read content_manifest.json: %s", exc)
    return {"folders": {}}


def _read_course_meta(rel_path: str) -> dict:
    """Read metadata.json for a course folder given its relative path."""
    if not rel_path:
        return {}
    meta_path = Path(SYLLABUS_DIR) / rel_path / "metadata.json"
    if meta_path.is_file():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _provision_trial_for_user(user_id: str) -> None:
    """
    Lazy-provision trial (always_active) entitlements for a user.

    Idempotent — safe to call on every request. Uses ON CONFLICT DO NOTHING
    so concurrent first-calls are safe without application-level locking.
    Only inserts rows for folder_keys that are not already present.
    """
    if not engine or not user_id:
        return
    try:
        manifest = _load_manifest()
        folders_map: dict = manifest.get("folders", {})

        with engine.begin() as conn:
            plans = conn.execute(
                text(
                    "SELECT plan_key, folder_keys "
                    "FROM ext_plans WHERE always_active = true"
                )
            ).fetchall()

            for plan_key, folder_keys_raw in plans:
                # SQLAlchemy returns JSONB as native Python list via psycopg2;
                # fall back to JSON parse for string representations.
                if isinstance(folder_keys_raw, list):
                    folder_keys = folder_keys_raw
                else:
                    try:
                        folder_keys = json.loads(folder_keys_raw or "[]")
                    except Exception:
                        folder_keys = []

                for fk in folder_keys:
                    rel_path = folders_map.get(fk, "")
                    meta = _read_course_meta(rel_path)
                    conn.execute(
                        text("""
                            INSERT INTO ext_user_entitlements
                                (user_id, exam_key, subject_key, folder_key,
                                 plan_key, state, activated_at)
                            VALUES
                                (:uid, :exam_key, :subject_key, :fk,
                                 :pk, 'unlocked', NOW())
                            ON CONFLICT (user_id, folder_key) DO NOTHING
                        """),
                        {
                            "uid": user_id,
                            "exam_key": meta.get("exam_key", ""),
                            "subject_key": meta.get("subject_key", ""),
                            "fk": fk,
                            "pk": plan_key,
                        },
                    )
    except Exception as exc:
        log.error(
            "ext_entitlements: trial provisioning failed for user %s: %s",
            user_id, exc,
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/entitlements/{user_id}")
async def get_entitlements(user_id: str, verified_user=_user_dep()):
    """
    Returns the authenticated user's full entitlement list.

    Lazy-provisions always_active (trial) entitlements on first call.
    The URL {user_id} parameter is accepted for client compatibility but the
    server always scopes results to the verified caller (HIGH-1 pattern).
    """
    started = time.monotonic()
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    resolved_uid = _resolve_user_id(verified_user, user_id)
    if not resolved_uid:
        raise HTTPException(status_code=401, detail="User identity unavailable")

    _provision_trial_for_user(resolved_uid)

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT folder_key, plan_key, state,
                           COALESCE(expires_at::text, '') AS expires_at
                    FROM ext_user_entitlements
                    WHERE user_id = :uid
                    ORDER BY folder_key
                """),
                {"uid": resolved_uid},
            ).fetchall()

        entitlements = [dict(r._mapping) for r in rows]
        _audit(
            user_id=resolved_uid,
            endpoint_type="entitlements_fetched",
            request_duration_ms=int((time.monotonic() - started) * 1000),
            status="ok",
            meta={"row_count": len(entitlements)},
        )
        return {"entitlements": entitlements}

    except Exception as exc:
        _audit(
            user_id=resolved_uid,
            endpoint_type="entitlements_fetched",
            request_duration_ms=int((time.monotonic() - started) * 1000),
            status="error",
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/access/check")
async def check_access(
    folder_key: str = Query(..., description="folder_key from metadata.json"),
    action: str = Query("generate", description="'generate' | 'history' | 'cache_hit'"),
    verified_user=_user_dep(),
):
    """
    Returns access state for one folder_key + action combination.

    Response: { "result": "allowed" | "blocked" | "expired", "plan_key": str | null }

    Gate rules:
      - action == 'history' or 'cache_hit'  →  always allowed (never gate history)
      - always_active plan                  →  always allowed (trial content)
      - state == 'unlocked' + not expired   →  allowed
      - state == 'unlocked' + expired       →  expired  (auto-marks state in DB)
      - state == 'locked' or no row         →  blocked
      - unauthenticated                     →  blocked
    """
    started = time.monotonic()

    # History and cache hits are never gated — return immediately.
    if action in ("history", "cache_hit"):
        return {"result": "allowed", "plan_key": None}

    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    resolved_uid = _resolve_user_id(verified_user, "")
    if not resolved_uid:
        _audit(
            user_id="anonymous",
            endpoint_type="access_check",
            request_duration_ms=int((time.monotonic() - started) * 1000),
            function=folder_key,
            status="blocked_unauthenticated",
        )
        return {"result": "blocked", "reason": "not_authenticated", "plan_key": None}

    # Ensure trial entitlements exist for this user before checking.
    _provision_trial_for_user(resolved_uid)

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT e.state, e.expires_at, p.always_active, e.plan_key
                    FROM ext_user_entitlements e
                    JOIN ext_plans p ON e.plan_key = p.plan_key
                    WHERE e.user_id = :uid AND e.folder_key = :fk
                    LIMIT 1
                """),
                {"uid": resolved_uid, "fk": folder_key},
            ).fetchone()

        if not row:
            _audit(
                user_id=resolved_uid,
                endpoint_type="access_check",
                request_duration_ms=int((time.monotonic() - started) * 1000),
                function=folder_key,
                status="blocked_no_entitlement",
            )
            return {"result": "blocked", "reason": "no_entitlement", "plan_key": None}

        state, expires_at, always_active, plan_key = row

        # Always_active plans (Trial) never expire.
        if always_active:
            _audit(
                user_id=resolved_uid,
                endpoint_type="access_check",
                request_duration_ms=int((time.monotonic() - started) * 1000),
                function=folder_key,
                status="allowed_trial",
            )
            return {"result": "allowed", "plan_key": plan_key}

        if state == "unlocked":
            now_utc = datetime.now(timezone.utc)
            if expires_at is None or expires_at.replace(tzinfo=timezone.utc) > now_utc:
                _audit(
                    user_id=resolved_uid,
                    endpoint_type="access_check",
                    request_duration_ms=int((time.monotonic() - started) * 1000),
                    function=folder_key,
                    status="allowed",
                )
                return {"result": "allowed", "plan_key": plan_key}

            # Subscription lapsed — mark expired in DB (best-effort, non-blocking).
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE ext_user_entitlements
                            SET state = 'expired'
                            WHERE user_id = :uid AND folder_key = :fk
                              AND state = 'unlocked'
                        """),
                        {"uid": resolved_uid, "fk": folder_key},
                    )
            except Exception as upd_exc:
                log.warning(
                    "ext_entitlements: could not mark expired for %s/%s: %s",
                    resolved_uid, folder_key, upd_exc,
                )
            _audit(
                user_id=resolved_uid,
                endpoint_type="access_check",
                request_duration_ms=int((time.monotonic() - started) * 1000),
                function=folder_key,
                status="expired",
            )
            return {"result": "expired", "plan_key": plan_key}

        _audit(
            user_id=resolved_uid,
            endpoint_type="access_check",
            request_duration_ms=int((time.monotonic() - started) * 1000),
            function=folder_key,
            status="blocked",
        )
        return {"result": "blocked", "plan_key": plan_key}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Phase 3 stub ──────────────────────────────────────────────────────────────

class ProvisionRequest(BaseModel):
    folder_key: str
    plan_key: str
    payment_ref: str = ""
    validity_days: int = 365


@router.post("/entitlements/provision")
async def provision_entitlement(
    req: ProvisionRequest,
    verified_user=_user_dep(),
):
    """
    Razorpay payment webhook — Phase 3.

    Will INSERT/UPDATE ext_user_entitlements for the paying user.
    Currently returns HTTP 501 to make the unimplemented state explicit
    and reserve the endpoint path before the payment gateway is wired up.
    """
    raise HTTPException(
        status_code=501,
        detail="Payment integration not yet implemented (Phase 3).",
    )

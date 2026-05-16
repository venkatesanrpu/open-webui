import os
import time
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text

# Open WebUI verified-user dependency.
#
# We try the canonical import path used by Open WebUI v0.9.x. If the symbol is
# unavailable (older/newer versions, partial overlay, smoke tests), we fall back
# to a permissive dependency that returns None. In that mode the endpoints will
# fall back to the legacy request-body / URL user_id to preserve compatibility.
try:  # pragma: no cover - import shape varies by upstream version
    from open_webui.utils.auth import get_verified_user as _get_verified_user
except Exception:  # pragma: no cover
    _get_verified_user = None

# Audit helper. Import is best-effort so the router still works on a partial
# overlay (e.g. local smoke test without the ext_authz module installed).
try:
    from open_webui.routers import ext_authz  # type: ignore
except Exception:  # pragma: no cover
    try:
        import ext_authz  # type: ignore
    except Exception:
        ext_authz = None  # type: ignore


def _user_dep():
    """
    Returns the upstream verified-user dependency if importable, otherwise a
    no-op dependency that yields None. Wrapping like this lets us keep a single
    `Depends(...)` call at the route signature regardless of environment.
    """
    if _get_verified_user is not None:
        return Depends(_get_verified_user)

    async def _noop():
        return None

    return Depends(_noop)


def _resolve_user_id(verified_user, fallback: str = "") -> str:
    """
    Prefer the server-derived user id when available. Falls back to the
    client-provided value only when the verified-user dependency is not wired
    (legacy overlay) so existing deployments keep working.
    """
    if verified_user is not None:
        uid = getattr(verified_user, "id", None)
        if uid:
            return str(uid)
    return fallback or ""


def _audit(**kwargs) -> None:
    """Thin guard around ext_authz.log_event so missing-module is a no-op."""
    if ext_authz is None:
        return
    try:
        ext_authz.log_event(**kwargs)
    except Exception:  # pragma: no cover - never raise into request path
        pass


router = APIRouter()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Initialize engine globally
engine = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL)
    except Exception as e:
        print(f"Ext Router: Failed to connect to database: {e}")

class TagRequest(BaseModel):
    chat_id: str
    # Kept for backwards compatibility with older clients. When the server can
    # derive the user from the verified-user dependency, the request-body value
    # is IGNORED. Treated as optional now so newer clients can omit it.
    user_id: str = ""
    data_function: str
    exam: str = "General"
    subject: str = "General"
    topic: str = "General"
    lesson: str = "General"
    concept: str = "General"
    level: str = ""
    number: str = ""

@router.post("/history/tag")
async def tag_chat(req: TagRequest, verified_user=_user_dep()):
    started = time.monotonic()
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    user_id = _resolve_user_id(verified_user, req.user_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="User identity unavailable")

    query = text("""
        INSERT INTO ext_chat_tags (
            chat_id, user_id, data_function,
            exam, subject, topic, lesson, concept,
            level, number
        )
        VALUES (
            :chat_id, :user_id, :data_function,
            :exam, :subject, :topic, :lesson, :concept,
            :level, :number
        )
        ON CONFLICT (chat_id) DO UPDATE SET
            data_function = EXCLUDED.data_function,
            exam = EXCLUDED.exam,
            subject = EXCLUDED.subject,
            topic = EXCLUDED.topic,
            lesson = EXCLUDED.lesson,
            concept = EXCLUDED.concept,
            level = EXCLUDED.level,
            number = EXCLUDED.number
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, {
                "chat_id": req.chat_id,
                "user_id": user_id,
                "data_function": req.data_function,
                "exam": req.exam,
                "subject": req.subject,
                "topic": req.topic,
                "lesson": req.lesson,
                "concept": req.concept,
                "level": req.level or "",
                "number": req.number or "",
            })
        _audit(
            user_id=user_id,
            endpoint_type="chat_tagged",
            request_duration_ms=int((time.monotonic() - started) * 1000),
            chat_id=req.chat_id,
            exam=req.exam,
            subject=req.subject,
            function=req.data_function,
            status="ok",
        )
        return {"status": "success"}
    except Exception as e:
        _audit(
            user_id=user_id,
            endpoint_type="chat_tagged",
            request_duration_ms=int((time.monotonic() - started) * 1000),
            chat_id=req.chat_id,
            exam=req.exam,
            subject=req.subject,
            function=req.data_function,
            status="error",
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/tags/{user_id}")
async def get_tags(user_id: str, verified_user=_user_dep()):
    started = time.monotonic()
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    # When the verified-user dependency is wired, ignore the URL parameter and
    # always scope results to the authenticated caller. The path param is kept
    # only to avoid breaking older frontend code that still encodes it.
    resolved_user_id = _resolve_user_id(verified_user, user_id)
    if not resolved_user_id:
        raise HTTPException(status_code=401, detail="User identity unavailable")

    # COALESCE so legacy rows (NULL level/number) return '' to the frontend,
    # making client-side identity comparisons null-safe.
    query = text("""
        SELECT
            chat_id,
            data_function,
            exam,
            subject,
            topic,
            lesson,
            concept,
            COALESCE(level, '')  AS level,
            COALESCE(number, '') AS number,
            created_at
        FROM ext_chat_tags
        WHERE user_id = :user_id
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"user_id": resolved_user_id})
            tags = [dict(row._mapping) for row in result]
            _audit(
                user_id=resolved_user_id,
                endpoint_type="history_fetched",
                request_duration_ms=int((time.monotonic() - started) * 1000),
                status="ok",
                meta={"row_count": len(tags)},
            )
            return {"tags": tags}
    except Exception as e:
        _audit(
            user_id=resolved_user_id,
            endpoint_type="history_fetched",
            request_duration_ms=int((time.monotonic() - started) * 1000),
            status="error",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/lookup")
async def lookup_chat(
    verified_user=_user_dep(),
    data_function: str = Query("", alias="data_function"),
    function: str = Query("", alias="function"),  # alias used by some clients
    exam: str = "General",
    subject: str = "General",
    topic: str = "General",
    lesson: str = "General",
    concept: str = "",
    level: str = "",
    number: str = "",
    user_id: str = "",
):
    """
    Server-side cache lookup for the Smart Router. Resolves a click identity
    tuple to an existing chat_id (or null). The frontend prefers this over the
    legacy `/history/tags/{user_id}` scan because it ships only one row over
    the wire and lets the database do the matching.

    `function` is accepted as an alias for `data_function` for client flexibility.
    """
    started = time.monotonic()
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")

    fn = data_function or function
    if not fn:
        raise HTTPException(status_code=400, detail="data_function is required")

    resolved_user_id = _resolve_user_id(verified_user, user_id)
    if not resolved_user_id:
        raise HTTPException(status_code=401, detail="User identity unavailable")

    query = text("""
        SELECT chat_id
        FROM ext_chat_tags
        WHERE user_id      = :user_id
          AND data_function = :data_function
          AND exam          = :exam
          AND subject       = :subject
          AND topic         = :topic
          AND lesson        = :lesson
          AND concept       = :concept
          AND COALESCE(level, '')  = :level
          AND COALESCE(number, '') = :number
        ORDER BY created_at DESC
        LIMIT 1
    """)

    try:
        with engine.connect() as conn:
            row = conn.execute(query, {
                "user_id": resolved_user_id,
                "data_function": fn,
                "exam": exam or "General",
                "subject": subject or "General",
                "topic": topic or "General",
                "lesson": lesson or "General",
                "concept": concept or "",
                "level": level or "",
                "number": number or "",
            }).fetchone()
            hit_chat_id = row[0] if row else None
            _audit(
                user_id=resolved_user_id,
                endpoint_type="lookup",
                request_duration_ms=int((time.monotonic() - started) * 1000),
                chat_id=hit_chat_id,
                exam=exam,
                subject=subject,
                function=fn,
                status="hit" if hit_chat_id else "miss",
            )
            return {"chat_id": hit_chat_id}
    except Exception as e:
        _audit(
            user_id=resolved_user_id,
            endpoint_type="lookup",
            request_duration_ms=int((time.monotonic() - started) * 1000),
            exam=exam,
            subject=subject,
            function=fn,
            status="error",
        )
        raise HTTPException(status_code=500, detail=str(e))

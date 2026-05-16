"""
ext_authz — modular authorization and audit helpers for the production overlay.

Responsibilities
----------------
* `resolve_user_id(...)`     — single source of truth for "who is this caller?",
                                preferring the Open WebUI verified-user dep,
                                falling back to a caller-supplied id, then
                                to the literal string ``"anonymous"``.
* `has_access(...)` /
  `require_access(...)`      — access scaffold. Currently allows every
                                authenticated user; Phase 3 (Razorpay / paid
                                plans) will plug `ext_user_access` checks in
                                here without changing call sites.
* `log_event(...)`           — fire-and-forget insert into ``ext_audit_logs``.
                                NEVER raises into the request path; an audit
                                failure must never surface as a 5xx.

Design notes
------------
* No prompt text and no PII is ever written to ``meta``. Callers are expected
  to pass only correlation-grade fields (exam, subject, function, status,
  request_id, chat_id, …).
* Token counts and cost columns were removed from the schema; this module
  intentionally has no token / cost accounting. Billing is observed via the
  Open WebUI admin panel and the vendor portals.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

log = logging.getLogger("ext_authz")

# ── Verified-user dependency import (mirrors ext_router) ──────────────────
try:  # pragma: no cover - import shape varies by upstream version
    from open_webui.utils.auth import get_verified_user as _get_verified_user
except Exception:  # pragma: no cover
    _get_verified_user = None


def user_dep():
    """
    Returns the upstream verified-user dependency if importable, otherwise a
    no-op dependency that yields None. Allows routers to keep one Depends()
    signature across overlay environments.
    """
    if _get_verified_user is not None:
        return Depends(_get_verified_user)

    async def _noop():
        return None

    return Depends(_noop)


def resolve_user_id(verified_user: Any, fallback: str = "") -> str:
    """
    Prefer the server-derived user id when available, fall back to the
    caller-supplied value (legacy path-param / body field), and finally to
    the literal ``"anonymous"`` so audit rows on unauthenticated routes still
    satisfy the NOT NULL constraint.
    """
    if verified_user is not None:
        uid = getattr(verified_user, "id", None)
        if uid:
            return str(uid)
    return fallback or "anonymous"


# ── Access scaffold ───────────────────────────────────────────────────────
def has_access(verified_user: Any, *, exam: str = "", subject: str = "") -> bool:
    """
    Returns True if the caller is authorized for the given (exam, subject).

    Phase 1 (now): every authenticated user is allowed. Anonymous callers are
    allowed for read-only static endpoints (the caller decides whether to
    require auth before calling this).

    Phase 3 (later): consult ``ext_user_access`` × ``ext_plans`` to enforce
    paid access. The signature already accepts exam / subject so call sites
    do not need to change when gating is enabled.
    """
    return True


def require_access(verified_user: Any, *, exam: str = "", subject: str = "") -> None:
    """
    Raises HTTPException(403) if the caller is not authorized.

    Currently a no-op gate (matches `has_access`). Kept as a separate symbol
    so future Phase 3 enforcement is a one-file change.
    """
    if not has_access(verified_user, exam=exam, subject=subject):
        raise HTTPException(status_code=403, detail="Access denied")


# ── Audit log writer ──────────────────────────────────────────────────────
_DATABASE_URL = os.getenv("DATABASE_URL", "")
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)

_engine: Engine | None = None
if _DATABASE_URL:
    try:
        _engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
    except Exception as e:  # pragma: no cover
        log.warning("ext_authz: failed to initialise audit engine: %s", e)
        _engine = None


def new_request_id() -> str:
    """Short opaque correlation id. Cheap to generate; safe to log."""
    return uuid.uuid4().hex[:16]


_INSERT_SQL = text("""
    INSERT INTO ext_audit_logs (
        user_id, endpoint_type, model, request_duration_ms,
        request_id, chat_id, exam, subject, function, status, meta
    ) VALUES (
        :user_id, :endpoint_type, :model, :request_duration_ms,
        :request_id, :chat_id, :exam, :subject, :function, :status,
        CAST(:meta AS JSONB)
    )
""")


def log_event(
    *,
    user_id: str,
    endpoint_type: str,
    model: str = "",
    request_duration_ms: int = 0,
    request_id: str | None = None,
    chat_id: str | None = None,
    exam: str | None = None,
    subject: str | None = None,
    function: str | None = None,
    status: str | None = None,
    meta: dict | None = None,
) -> None:
    """
    Insert a single audit row. Swallows ALL exceptions — audit failures must
    not surface as 5xx on the user-facing request. Callers should treat this
    as fire-and-forget.

    `meta` MUST NOT contain prompt text or user PII. Use it for short
    correlation hints only (e.g. ``{"alias_used": "function"}``).
    """
    if _engine is None:
        return

    try:
        import json
        meta_json = json.dumps(meta) if meta else None
        with _engine.begin() as conn:
            conn.execute(_INSERT_SQL, {
                "user_id": user_id or "anonymous",
                "endpoint_type": endpoint_type,
                "model": model or "",
                "request_duration_ms": int(request_duration_ms or 0),
                "request_id": request_id,
                "chat_id": chat_id,
                "exam": exam,
                "subject": subject,
                "function": function,
                "status": status,
                "meta": meta_json,
            })
    except Exception as e:  # pragma: no cover - defensive; never raise
        log.warning("ext_authz.log_event failed (%s): %s", endpoint_type, e)

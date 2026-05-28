"""Auth dependency (spec Ch 1.1 / 10.6).

Permissive by default so the single-tenant beta keeps working with no tokens.
When AUTH_ENFORCED=true, validates a Supabase-issued `Authorization: Bearer
<JWT>` (HS256, signed with SUPABASE_JWT_SECRET) and resolves (user_id, org_id).
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from energy_modeler.config import settings

from .models import DEFAULT_ORG_ID

# auto_error=False: we surface the spec error envelope ourselves, not FastAPI's.
_bearer = HTTPBearer(auto_error=False)

DEV_IDENTITY_USER = "00000000-0000-0000-0000-0000000000de"


@dataclass
class Identity:
    user_id: str
    org_id: str
    email: str | None = None


def _unauthorized(message: str) -> "Exception":
    from fastapi import HTTPException

    return HTTPException(
        status_code=401,
        detail={"error": message, "code": "AUTH_REQUIRED"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Identity:
    """FastAPI dependency. Returns the caller Identity.

    Beta (AUTH_ENFORCED unset/false): returns a default single-org identity so
    existing routes work without a token. Production: requires a valid JWT."""
    if not settings.auth_enforced:
        return Identity(user_id=DEV_IDENTITY_USER, org_id=DEFAULT_ORG_ID)

    if creds is None or not creds.credentials:
        raise _unauthorized("Authentication required")
    if not settings.supabase_jwt_secret:
        # Misconfiguration: enforcement on but no secret to verify against.
        raise _unauthorized("Auth not configured")

    import jwt  # PyJWT; only needed on the enforced path

    try:
        payload = jwt.decode(
            creds.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError:
        raise _unauthorized("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise _unauthorized("Token missing subject")
    org_id = (payload.get("app_metadata") or {}).get("org_id") or DEFAULT_ORG_ID
    request.state.user_id = user_id
    return Identity(user_id=user_id, org_id=org_id, email=payload.get("email"))

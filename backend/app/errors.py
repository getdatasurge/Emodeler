"""Standard error envelope + request-id correlation (spec Ch 10.6 / build §3.3).

Every error response is shaped:
    {"error": str, "code": str, "details": {...}?, "request_id": "req_..."}
Routers may raise HTTPException with either a plain string detail or a dict
carrying {error, code, details}; both are normalized here."""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# HTTP status -> default error code (overridable per-raise via detail['code']).
STATUS_CODE = {
    400: "BAD_REQUEST",
    401: "AUTH_REQUIRED",
    403: "AUTH_FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_FAILED",
    429: "RATE_LIMIT",
    500: "INTERNAL",
    502: "UPSTREAM_ERROR",
}


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = rid
    return rid


def _envelope(error: str, code: str, details, request_id: str) -> dict:
    body = {"error": error, "code": code, "request_id": request_id}
    if details is not None:
        body["details"] = details
    return body


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


def install_error_handling(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException):
        rid = _request_id(request)
        detail = exc.detail
        if isinstance(detail, dict):
            error = detail.get("error") or detail.get("message") or "Request failed"
            code = detail.get("code") or STATUS_CODE.get(exc.status_code, "ERROR")
            details = detail.get("details")
        else:
            error = str(detail)
            code = STATUS_CODE.get(exc.status_code, "ERROR")
            details = None
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(error, code, details, rid),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError):
        rid = _request_id(request)
        return JSONResponse(
            status_code=422,
            content=_envelope("Validation failed", "VALIDATION_FAILED", exc.errors(), rid),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exc(request: Request, exc: Exception):
        # Sentry (if configured) captures the traceback via its own integration.
        rid = _request_id(request)
        return JSONResponse(
            status_code=500,
            content=_envelope("Internal server error", "INTERNAL", None, rid),
        )

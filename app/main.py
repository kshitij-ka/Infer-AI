import logging

from fastapi import Depends, FastAPI, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.deps import get_redis
from app.api.routes import admin, auth, chat
from app.core.body_limit import add_body_size_limit_middleware
from app.core.config import get_settings
from app.core.logging import add_request_id_middleware, configure_logging
from app.core.login_rate_limit import add_login_ip_rate_limit_middleware
from app.core.middleware import SECURITY_HEADERS, add_security_headers_middleware
from app.db.session import get_db
from app.services.metrics import render_metrics

# Field names treated as sensitive across every request body schema in this
# application. The raw "input" value FastAPI's default validation error
# handler echoes back must never include the submitted value for any of
# these fields. Currently "password" is the only such field (used by
# LoginRequest and CreateUserRequest); if a new schema adds another
# sensitive field (an API key, a token, etc), add its name here.
SENSITIVE_FIELD_NAMES = {"password"}

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)

# Starlette runs middleware in the reverse of the order it is added here:
# the last middleware added is the outermost layer and therefore the first
# to see an incoming request and the last to see the outgoing response.
# With the registration order below (request id, then login IP rate
# limit, then body size limit, then security headers, then CORS), the
# actual per-request execution order is:
#   1. CORSMiddleware (outermost, added last): handles preflight
#      OPTIONS requests and stamps CORS response headers.
#   2. SecurityHeadersMiddleware: stamps the fixed security headers
#      onto whatever response the inner layers produce.
#   3. BodySizeLimitMiddleware: counts request body bytes and rejects
#      oversized bodies before they reach routing or request body
#      parsing.
#   4. LoginIPRateLimitMiddleware: for POST /auth/login only, checks a
#      per-client-IP rate limit before any request body parsing or
#      Pydantic validation happens, so a malformed body (one that
#      would otherwise fail LoginRequest validation with a 422 before
#      the route function body, and therefore before its own
#      per-username-and-IP rate limit check, ever runs) still counts
#      against a rate limit. This must sit inside (run after)
#      BodySizeLimitMiddleware, since an oversized body should still
#      get its own 413 rather than consuming a login rate limit slot,
#      and outside (run before) RequestIdMiddleware is not required
#      but keeps ordering simple, since this layer does not need the
#      request id.
#   5. RequestIdMiddleware (innermost, added first): assigns the
#      request id and logs the request summary line, so every other
#      layer, plus the exception handlers, run with the request id
#      already set in request_id_var.
# On the way out, responses pass back through this stack in the
# opposite order (request id's header attachment first, then login IP
# rate limit, then body size limit, then security headers, then CORS).
# Reordering these add_middleware calls changes which layer sees a
# request or response first, so do not reorder them without
# re-checking this comment and the tests in tests/test_body_limit.py,
# tests/test_security_headers.py, tests/test_cors.py,
# tests/test_request_id.py, and tests/test_login_rate_limit.py.
add_request_id_middleware(app)

add_login_ip_rate_limit_middleware(
    app, limit_per_minute=settings.ip_only_login_rate_limit_per_minute
)

add_body_size_limit_middleware(app, max_bytes=settings.max_request_body_bytes)

add_security_headers_middleware(app)

allowed_origins = [
    origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(admin.router)

logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches any exception not handled by a more specific handler,
    logs the full detail server side, and returns a body containing
    no exception message or type, so internal detail never reaches
    the client.

    Args:
        request: the request that triggered the exception.
        exc: the exception that was raised.

    Returns:
        A 500 JSON response with a fixed, generic detail message and
        the same baseline security headers every other response
        carries.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    for header_name, header_value in SECURITY_HEADERS.items():
        response.headers[header_name] = header_value
    return response


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Replaces FastAPI's default request validation error response with a
    sanitized version.

    FastAPI's default handler for RequestValidationError echoes the raw
    "input" value for every field that failed validation. For a field
    such as "password" that only has length constraints, this means a
    password that is too short or too long gets echoed back verbatim in
    the 422 response body, leaking the plaintext password into any
    logging surface that captures response bodies (load balancer access
    logs, client side error trackers, browser dev tools, shared
    terminals).

    This handler keeps the field location and the validation message for
    every error (so the client still learns which field failed and why),
    but drops the "input" key for any field listed in
    SENSITIVE_FIELD_NAMES, while leaving "input" intact for every other
    field.

    Args:
        request: the request that failed validation.
        exc: the validation error raised by FastAPI/Pydantic.

    Returns:
        A 422 JSON response with the same overall shape FastAPI normally
        returns, except sensitive fields never carry an "input" key.
    """
    sanitized_errors = []
    for error in exc.errors():
        loc = error.get("loc", ())
        field_name = loc[-1] if loc else None
        sanitized_error = {k: v for k, v in error.items() if k != "input"}
        if field_name not in SENSITIVE_FIELD_NAMES and "input" in error:
            sanitized_error["input"] = error["input"]
        sanitized_errors.append(sanitized_error)

    content = jsonable_encoder({"detail": sanitized_errors})
    response = JSONResponse(status_code=422, content=content)
    for header_name, header_value in SECURITY_HEADERS.items():
        response.headers[header_name] = header_value
    return response


@app.get("/health")
def health(db: Session = Depends(get_db), redis_client=Depends(get_redis)) -> dict:
    checks = {"database": "ok", "redis": "ok"}

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"

    try:
        redis_client.ping()
    except Exception:
        checks["redis"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


@app.get("/metrics")
def metrics() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)

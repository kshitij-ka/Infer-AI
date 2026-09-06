import logging

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.deps import get_redis
from app.api.routes import admin, auth, chat
from app.core.body_limit import add_body_size_limit_middleware
from app.core.config import get_settings
from app.core.middleware import SECURITY_HEADERS, add_security_headers_middleware
from app.db.session import get_db
from app.services.metrics import render_metrics

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(title=settings.app_name)

# Starlette runs middleware in the reverse of the order it is added here:
# the last middleware added is the outermost layer and therefore the first
# to see an incoming request and the last to see the outgoing response.
# With the registration order below (body size limit, then security
# headers, then CORS), the actual per-request execution order is:
#   1. CORSMiddleware (outermost, added last): handles preflight
#      OPTIONS requests and stamps CORS response headers.
#   2. SecurityHeadersMiddleware: stamps the fixed security headers
#      onto whatever response the inner layers produce.
#   3. BodySizeLimitMiddleware (innermost, added first): counts
#      request body bytes and rejects oversized bodies before they
#      reach routing or request body parsing.
# On the way out, responses pass back through this stack in the
# opposite order (body size limit's own early responses first, then
# security headers, then CORS). Reordering these add_middleware calls
# changes which layer sees a request or response first, so do not
# reorder them without re-checking this comment and the tests in
# tests/test_body_limit.py, tests/test_security_headers.py, and
# tests/test_cors.py.
add_body_size_limit_middleware(app, max_bytes=settings.max_request_body_bytes)

add_security_headers_middleware(app)

allowed_origins = [
    origin.strip()
    for origin in settings.cors_allowed_origins.split(",")
    if origin.strip()
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

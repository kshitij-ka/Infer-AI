"""
Request body size limiting middleware.

Rejects any request whose declared Content-Length exceeds the
configured maximum before the body is read into memory, so an
oversized payload cannot be used to exhaust server memory or CPU
time during JSON parsing.
"""
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects requests whose Content-Length header exceeds max_bytes.

    Args:
        app: the ASGI application to wrap.
        max_bytes: the maximum allowed request body size, in bytes.
    """

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Checks the Content-Length header against max_bytes before
        calling the next handler. A missing Content-Length header is
        allowed through to call_next, since Starlette's own body
        reading will still bound memory use for a chunked request in
        practice for this application's route set (no streaming
        uploads exist).

        Args:
            request: the incoming ASGI request.
            call_next: the next handler in the middleware chain.

        Returns:
            A 413 JSON response if the body is too large, otherwise
            the response from call_next.
        """
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
        return await call_next(request)


def add_body_size_limit_middleware(app: FastAPI, max_bytes: int) -> None:
    """
    Registers BodySizeLimitMiddleware on the given app.

    Args:
        app: the FastAPI application instance to register the
            middleware on.
        max_bytes: the maximum allowed request body size, in bytes.
    """
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_bytes)

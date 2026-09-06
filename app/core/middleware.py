"""
Security related ASGI middleware.

Holds middleware that applies to every request regardless of route,
such as response security headers. Kept separate from main.py so
main.py stays focused on wiring routers together.
"""

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds a fixed set of security response headers to every response.

    This is a JSON API with no HTML rendering, so the Content
    Security Policy denies everything by default rather than
    allowing specific sources, since there is nothing on this server
    that needs to load a script, style, or frame.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Runs the next handler in the chain, then stamps the security
        headers onto whatever response it returns.

        Args:
            request: the incoming ASGI request.
            call_next: the next handler in the middleware chain.

        Returns:
            The response from call_next, with security headers added.
        """
        response = await call_next(request)
        for header_name, header_value in SECURITY_HEADERS.items():
            response.headers[header_name] = header_value
        return response


def add_security_headers_middleware(app: FastAPI) -> None:
    """
    Registers SecurityHeadersMiddleware on the given app.

    Args:
        app: the FastAPI application instance to register the
            middleware on.
    """
    app.add_middleware(SecurityHeadersMiddleware)

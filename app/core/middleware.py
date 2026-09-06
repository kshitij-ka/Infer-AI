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

# This app now also serves a static frontend (app/static/, mounted in
# main.py) alongside its JSON API, so the CSP can no longer deny
# everything: it allows only the specific sources that frontend
# actually needs (self-hosted CSS/JS/images, same-origin fetch() calls
# to the API, and the Google Fonts CDN that tokens.css imports) and
# keeps every other directive at 'none'.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'none'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds a fixed set of security response headers to every response.

    The Content Security Policy defaults to denying everything and
    then allows only the specific sources the static frontend
    (app/static/) actually needs: same-origin scripts, styles, images,
    and fetch() calls, plus the Google Fonts CDN that tokens.css
    imports. style-src also allows 'unsafe-inline' because both static
    pages define their page-specific layout in a plain <style> block
    rather than a second external stylesheet; this is safe here since
    neither page ever writes user- or LLM-controlled text into a
    <style> tag or a style="" attribute (chat answers and usernames
    are inserted via textContent, which style-src has no bearing on
    either way). Every other directive stays at 'none'.
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

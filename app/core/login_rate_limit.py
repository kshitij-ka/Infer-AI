"""
Per-IP login rate limit middleware.

Protects POST /auth/login against a bypass of the route level, per
username and IP, rate limit check in app/api/routes/auth.py. That
check only runs inside the login() route function body, after
FastAPI has already validated the request body against the
LoginRequest Pydantic model. A request whose body fails that
validation (a missing password field, a non-string password, a
missing username) never reaches the route function body at all, so
it gets a 422 response without the rate limiter ever being
consulted. An attacker can send an unlimited number of malformed
requests for free this way, defeating the point of the rate limiter
on the exact endpoint it exists to protect.

This middleware closes that gap by keying a rate limit check on
client IP alone and running it before FastAPI attempts to parse or
validate the request body at all, so the check applies regardless of
whether the body later turns out to be well formed. It only applies
to POST /auth/login and deliberately uses a higher threshold than the
existing per-username-and-IP check, since one IP can legitimately
host many different accounts logging in (a shared office network or
NAT), and the per-account check inside the route function body
remains the more precise layer for well formed requests.
"""

from fastapi import FastAPI

from app.services.cache import get_redis_client, is_rate_limited

LOGIN_PATH = "/auth/login"
TOO_MANY_REQUESTS_MESSAGE = b'{"detail":"Too many login attempts, please try again later"}'


def _build_ip_only_login_rate_limit_key(client_ip: str) -> str:
    """
    Builds a rate limit key for a client IP alone, for the login
    endpoint. Uses a loginip: prefix, distinct from the login:
    prefix the route level per-username-and-IP check uses and from
    any other existing key namespace, so the two layers never read
    or write the same Redis counter.

    Args:
        client_ip: the client IP address read from the ASGI scope.

    Returns:
        A deterministic rate limit key string for this client IP.
    """
    return f"loginip:{client_ip}"


def _extract_client_ip(scope) -> str:
    """
    Reads the client IP address out of an ASGI connection scope.

    Args:
        scope: the ASGI connection scope for an http request.

    Returns:
        The client IP address string, or "unknown" if the scope does
        not carry client connection information.
    """
    client = scope.get("client")
    if not client:
        return "unknown"
    return str(client[0])


class LoginIPRateLimitMiddleware:
    """
    Pure ASGI middleware that rate limits POST /auth/login by client
    IP alone, before request body parsing or validation occurs.

    Args:
        app: the ASGI application to wrap.
        limit_per_minute: the maximum number of POST /auth/login
            requests allowed per client IP per minute, regardless of
            whether each request's body is well formed.
    """

    def __init__(self, app, limit_per_minute: int) -> None:
        self.app = app
        self.limit_per_minute = limit_per_minute

    async def __call__(self, scope, receive, send) -> None:
        """
        Handles one ASGI request/response cycle, enforcing the per-IP
        login rate limit only for POST /auth/login, and passing
        everything else through unchanged.

        Args:
            scope: the ASGI connection scope.
            receive: the ASGI receive callable.
            send: the ASGI send callable.
        """
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != LOGIN_PATH
        ):
            await self.app(scope, receive, send)
            return

        client_ip = _extract_client_ip(scope)
        redis_client = get_redis_client()
        rate_limit_key = _build_ip_only_login_rate_limit_key(client_ip)

        if is_rate_limited(
            redis_client,
            key=rate_limit_key,
            limit_per_minute=self.limit_per_minute,
        ):
            await _send_json_response(send, 429, TOO_MANY_REQUESTS_MESSAGE)
            return

        await self.app(scope, receive, send)


async def _send_json_response(send, status_code: int, body: bytes) -> None:
    """
    Sends a complete minimal JSON response directly through the raw
    ASGI send callable.

    Args:
        send: the ASGI send callable.
        status_code: the HTTP status code to send.
        body: the raw JSON response body bytes to send.
    """
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def add_login_ip_rate_limit_middleware(app: FastAPI, limit_per_minute: int) -> None:
    """
    Registers LoginIPRateLimitMiddleware on the given app.

    Args:
        app: the FastAPI application instance to register the
            middleware on.
        limit_per_minute: the maximum number of POST /auth/login
            requests allowed per client IP per minute.
    """
    app.add_middleware(LoginIPRateLimitMiddleware, limit_per_minute=limit_per_minute)

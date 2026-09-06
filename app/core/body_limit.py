"""
Request body size limiting middleware.

Rejects any request whose body exceeds the configured maximum before
it is passed on to route handling, so an oversized payload cannot be
used to exhaust server memory or CPU time during JSON parsing. This
is implemented as a pure ASGI middleware, not a BaseHTTPMiddleware
subclass, because the enforcement has to count bytes as they stream
in off the wire. A request can omit Content-Length entirely (for
example with Transfer-Encoding: chunked) or send a Content-Length
header that understates the real body size, so the header alone
cannot be trusted as the only check.
"""
from fastapi import FastAPI

MAX_BYTES_EXCEEDED_MESSAGE = b'{"detail":"Request body too large"}'
INVALID_CONTENT_LENGTH_MESSAGE = b'{"detail":"Invalid Content-Length header"}'


class BodySizeLimitMiddleware:
    """
    Pure ASGI middleware that enforces a maximum request body size.

    A present and honest Content-Length header is checked immediately
    as a fast path rejection. The real enforcement, however, is done
    by wrapping the ASGI receive callable and counting the bytes of
    every "http.request" message actually delivered to the
    application, so the limit holds even when Content-Length is
    absent (chunked transfer encoding) or lying.

    Args:
        app: the ASGI application to wrap.
        max_bytes: the maximum allowed request body size, in bytes.
    """

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        """
        Handles one ASGI request/response cycle, enforcing the body
        size limit for http scopes and passing everything else
        through unchanged.

        Args:
            scope: the ASGI connection scope.
            receive: the ASGI receive callable.
            send: the ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                content_length_int = int(content_length)
            except ValueError:
                await _send_json_response(send, 400, INVALID_CONTENT_LENGTH_MESSAGE)
                return
            if content_length_int > self.max_bytes:
                await _send_json_response(send, 413, MAX_BYTES_EXCEEDED_MESSAGE)
                return

        state = {"total": 0, "rejected": False, "response_sent": False}

        async def limited_receive():
            """
            Wraps the ASGI receive callable to count body bytes across
            every "http.request" message as they actually arrive, so
            the running total is enforced regardless of what any
            Content-Length header claimed. As soon as the running
            total exceeds max_bytes, the 413 response is sent
            immediately through the raw send callable, since the
            wrapped application (Starlette/FastAPI) catches a plain
            disconnect internally and would otherwise produce its own
            400 response instead of letting this middleware answer.

            Returns:
                The next ASGI message, unchanged, unless the running
                body byte total has exceeded max_bytes, in which case
                a synthetic disconnect message is returned instead so
                the application stops reading further body chunks.
            """
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                state["total"] += len(body)
                if state["total"] > self.max_bytes and not state["rejected"]:
                    state["rejected"] = True
                    await _send_json_response(send, 413, MAX_BYTES_EXCEEDED_MESSAGE)
                    state["response_sent"] = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            """
            Forwards ASGI response messages to the real send callable,
            except once this middleware has already sent its own 413
            response, in which case any further messages the wrapped
            application tries to send are discarded, since a second
            response start/body pair would violate the ASGI protocol.

            Args:
                message: the ASGI response message the wrapped
                    application is trying to send.
            """
            if state["response_sent"]:
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if state["rejected"]:
                return
            raise


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


def add_body_size_limit_middleware(app: FastAPI, max_bytes: int) -> None:
    """
    Registers BodySizeLimitMiddleware on the given app.

    Args:
        app: the FastAPI application instance to register the
            middleware on.
        max_bytes: the maximum allowed request body size, in bytes.
    """
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_bytes)

"""
Structured logging setup.

Configures the root logger to emit single line JSON records instead
of the default plain text format, so logs are easy to grep and feed
into a log aggregator without a separate parsing step. Also provides
RequestIdMiddleware, which assigns a UUID per request, attaches it
to the response as a header, and makes it available to log records
emitted while handling that request through a context variable.
"""
import json
import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    """Formats a log record as a single line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Builds the JSON log line for the given record, including the
        current request id from request_id_var if one is set.

        Args:
            record: the log record to format.

        Returns:
            A single line JSON string.
        """
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(log_level: str) -> None:
    """
    Replaces the root logger's handlers with a single stream handler
    using JsonFormatter, at the given level.

    Args:
        log_level: the minimum level to log, as a string such as
            "INFO" or "DEBUG".
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Assigns a UUID to every request, exposes it through
    request_id_var for the duration of the request so log records
    emitted while handling it include the same id, and attaches it
    to the response as the X-Request-ID header. Also logs one line
    per request with the method, path, status code, and latency.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Generates a request id, stores it in the context variable,
        times the request, logs a summary line, and attaches the id
        to the response header.

        Args:
            request: the incoming ASGI request.
            call_next: the next handler in the middleware chain.

        Returns:
            The response from call_next, with the X-Request-ID
            header added.
        """
        request_id = str(uuid.uuid4())
        token = request_id_var.set(request_id)
        logger = logging.getLogger("app.request")
        start = time.perf_counter()

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s (%.2fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        request_id_var.reset(token)
        return response


def add_request_id_middleware(app: FastAPI) -> None:
    """
    Registers RequestIdMiddleware on the given app.

    Args:
        app: the FastAPI application instance to register the
            middleware on.
    """
    app.add_middleware(RequestIdMiddleware)

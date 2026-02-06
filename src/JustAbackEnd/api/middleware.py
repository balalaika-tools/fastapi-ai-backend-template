import time
import uuid
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send
from JustAbackEnd.core.logger import CorrelationCtx, get_logger
from JustAbackEnd.core.constants import LOGGER_NAME, CORRELATION_ID_HEADER

logger = get_logger(f"{LOGGER_NAME}.{__name__}")


class CorrelationIdMiddleware:
    # Pure ASGI middleware — avoids BaseHTTPMiddleware overhead and streaming issues.

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        correlation_id = _extract_or_generate_id(scope)
        token = CorrelationCtx.set(correlation_id)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append(CORRELATION_ID_HEADER, correlation_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            CorrelationCtx.reset(token)


class RequestLoggingMiddleware:
    # Pure ASGI middleware for request/response logging.

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        method = scope.get("method", "?")
        path = scope.get("path", "?")
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        logger.debug(
            f"📥 {method}",
            extra={"method": method, "path": path, "client_ip": client_ip},
        )

        status_code = 0

        async def send_with_logging(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, send_with_logging)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            icon = "✅" if 0 < status_code < 400 else "⚠️"
            logger.debug(
                f"📤 {icon} {method}",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
            )


def _extract_or_generate_id(scope: Scope) -> str:
    header_key = CORRELATION_ID_HEADER.lower().encode()
    for key, value in scope.get("headers", []):
        if key == header_key:
            return value.decode()
    return str(uuid.uuid4())

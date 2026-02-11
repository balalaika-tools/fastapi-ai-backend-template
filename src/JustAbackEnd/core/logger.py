import atexit
import json
import logging
import os
import socket
import sys
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from queue import Empty, Full, Queue
from typing import ClassVar, Optional, Union


# ============================================================
# Custom TRACING level  (between WARNING=30 and ERROR=40)
# ============================================================

TRACING = 35
logging.addLevelName(TRACING, "TRACING")


def _tracing(self: logging.Logger, message, *args, **kwargs):
    """Log a message at the TRACING level (numeric 35).

    Use for high-visibility trace points that must survive production
    log-level filtering (WARNING+).  Easily searchable for bulk
    comment/uncomment via ``\\.tracing(`` or ``TRACING``.
    """
    if self.isEnabledFor(TRACING):
        self._log(TRACING, message, args, **kwargs)


logging.Logger.tracing = _tracing  # type: ignore[attr-defined]


# ============================================================
# Correlation ID context
# ============================================================

class CorrelationCtx:
    """Thread/task-safe correlation ID backed by a ``ContextVar``.

    Works correctly across ``asyncio`` tasks and OS threads.
    Use :meth:`use` as a context manager to scope a correlation ID::

        with CorrelationCtx.use("req-abc-123"):
            logger.info("handling request")
    """

    _cid: ClassVar[ContextVar[Optional[str]]] = ContextVar(
        "correlation_id", default=None
    )

    @classmethod
    def get(cls) -> Optional[str]:
        return cls._cid.get()

    @classmethod
    def set(cls, cid: Optional[str]):
        return cls._cid.set(cid)

    @classmethod
    def reset(cls, token):
        cls._cid.reset(token)

    @classmethod
    @contextmanager
    def use(cls, cid: Optional[str]):
        token = cls.set(cid)
        try:
            yield
        finally:
            cls.reset(token)


class CorrelationIdFilter(logging.Filter):
    """Injects the current correlation ID into every log record.

    Must be attached to the ``QueueHandler`` (not to output handlers) so it
    captures the ``ContextVar`` value on the **calling** thread/task.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "correlation_id", None):
            record.correlation_id = CorrelationCtx.get() or "-"
        return True


# ============================================================
# JSON formatter
# ============================================================

class JsonFormatter(logging.Formatter):
    _MAX_SERIALIZE_DEPTH = 8
    _STANDARD_KEYS = frozenset({
        "name", "msg", "args", "created", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs",
        "message", "pathname", "process", "processName",
        "relativeCreated", "thread", "threadName",
        "stack_info", "exc_info", "exc_text", "asctime",
        "correlation_id",
    })

    def __init__(
        self,
        *,
        include_runtime_fields: bool = True,
        max_value_length: int = 2000,
    ):
        super().__init__()
        self._include_runtime_fields = include_runtime_fields
        self._max_value_length = max(0, int(max_value_length))
        self._hostname = socket.gethostname()

    def formatTime(self, record, datefmt=None):
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    # -- serialization helpers --------------------------------

    def _make_json_serializable(self, obj):
        from datetime import datetime, date
        from uuid import UUID

        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, Path):
            return str(obj)
        if hasattr(obj, "__dict__"):
            try:
                return str(obj)
            except Exception:
                return repr(obj)
        return obj

    def _serialize_value(self, value, _depth=0):
        if _depth >= self._MAX_SERIALIZE_DEPTH:
            return self._safe_str(value)
        if isinstance(value, dict):
            return {
                k: self._serialize_value(v, _depth + 1)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(v, _depth + 1) for v in value]
        return self._make_json_serializable(value)

    def _truncate_value(self, value: str) -> str:
        if self._max_value_length <= 0:
            return value
        if len(value) <= self._max_value_length:
            return value
        return value[: self._max_value_length] + "...(truncated)"

    def _safe_str(self, value) -> str:
        try:
            text = str(value)
        except Exception:
            try:
                text = repr(value)
            except Exception:
                text = "<unrepresentable>"
        return self._truncate_value(text)

    # -- format -----------------------------------------------

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
            "correlation_id": getattr(record, "correlation_id", "-"),
        }

        for key, value in record.__dict__.items():
            if key not in self._STANDARD_KEYS:
                try:
                    data[key] = self._serialize_value(value)
                except Exception:
                    data[key] = self._safe_str(value)

        if self._include_runtime_fields:
            data["process_name"] = getattr(record, "processName", None)
            data["pid"] = record.process
            data["thread_name"] = getattr(record, "threadName", None)
            data["thread_id"] = record.thread
            data["hostname"] = self._hostname

        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)

        return json.dumps(data, ensure_ascii=False, default=self._safe_str)


# ============================================================
# Queue handler (non-blocking drop)
# ============================================================

class DroppingQueueHandler(QueueHandler):
    """``QueueHandler`` that drops records instead of blocking when full."""

    _DROP_LOG_INTERVAL = 1000

    def __init__(self, queue: Queue):
        super().__init__(queue)
        self.dropped_count = 0

    def enqueue(self, record):
        try:
            self.queue.put_nowait(record)
        except Full:
            self.dropped_count += 1
            if (
                self.dropped_count == 1
                or self.dropped_count % self._DROP_LOG_INTERVAL == 0
            ):
                sys.stderr.write(
                    f"[logging] Queue full: {self.dropped_count} log records "
                    f"dropped so far\n"
                )


# ============================================================
# Webhook handler
# ============================================================

class WebhookHandler(logging.Handler):
    """Sends formatted log records to a webhook URL via a background thread.

    Records are queued non-blocking in :meth:`emit` and delivered by a
    dedicated worker thread using a synchronous HTTP client, so neither
    the calling thread nor any ``asyncio`` event loop is ever blocked by
    network I/O.

    Requires the ``httpx`` package (imported lazily on first use).
    """

    _SENTINEL = None

    def __init__(
        self,
        url: str,
        *,
        timeout: float = 5.0,
        level: int = logging.ERROR,
        queue_size: int = 1000,
    ):
        super().__init__(level)
        import httpx  # fail-fast: verify httpx is installed

        self._httpx = httpx
        self._url = url
        self._timeout = timeout
        self._send_queue: Queue[Optional[str]] = Queue(maxsize=queue_size)
        self._stop_event = threading.Event()
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="webhook-log-worker",
            daemon=True,
        )
        self._worker.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._send_queue.put_nowait(msg)
        except Full:
            sys.stderr.write("[logging] Webhook queue full — dropping record\n")
        except Exception:
            self.handleError(record)

    def _worker_loop(self) -> None:
        client = self._httpx.Client(timeout=self._timeout)
        try:
            while True:
                try:
                    msg = self._send_queue.get(timeout=0.5)
                except Empty:
                    if self._stop_event.is_set():
                        break
                    continue
                if msg is self._SENTINEL:
                    break
                try:
                    client.post(
                        self._url,
                        content=msg,
                        headers={"Content-Type": "application/json"},
                    )
                except Exception as exc:
                    sys.stderr.write(
                        f"[logging] Webhook send failed: {exc}\n"
                    )
        finally:
            client.close()

    def close(self) -> None:
        self._stop_event.set()
        try:
            self._send_queue.put(self._SENTINEL, timeout=5)
        except Full:
            pass  # stop_event will cause worker to exit after draining
        self._worker.join(timeout=10)
        super().close()


# ============================================================
# Listener lifecycle
# ============================================================

_active_listeners: dict[str, QueueListener] = {}
_atexit_registered = False


def _stop_and_close_listener(listener: Optional[QueueListener]) -> None:
    if not listener:
        return
    try:
        listener.stop()
    except Exception:
        pass
    for handler in getattr(listener, "handlers", ()):
        try:
            handler.close()
        except Exception:
            pass


def _atexit_shutdown_all() -> None:
    for listener in list(_active_listeners.values()):
        _stop_and_close_listener(listener)
    _active_listeners.clear()


def shutdown_logging(logger_name: str = "gLogger") -> None:
    """Stop the queue listener and close all handlers for *logger_name*.

    Call this during application shutdown (e.g. in a FastAPI lifespan
    shutdown hook).  It is safe to call multiple times.
    """
    listener = _active_listeners.pop(logger_name, None)
    if listener:
        _stop_and_close_listener(listener)


# ============================================================
# Internal helpers
# ============================================================

def _is_project_logger(logger_name: str, name: str) -> bool:
    return name == logger_name or name.startswith(f"{logger_name}.")


def _configure_external_loggers(
    *,
    logger_name: str,
    mode: str,
) -> None:
    for name, logger_obj in list(logging.root.manager.loggerDict.items()):
        if isinstance(logger_obj, logging.PlaceHolder):
            continue
        if not isinstance(logger_obj, logging.Logger):
            continue
        if _is_project_logger(logger_name, name):
            continue

        if mode == "disable":
            logger_obj.handlers.clear()
            logger_obj.propagate = False
            logger_obj.disabled = True
        elif mode == "propagate":
            logger_obj.handlers.clear()
            logger_obj.propagate = True
            logger_obj.disabled = False
            logger_obj.setLevel(logging.NOTSET)
        elif mode == "keep":
            logger_obj.disabled = False


def _create_queue_handler(
    queue_maxsize: Optional[int],
) -> tuple[Queue, DroppingQueueHandler]:
    # None / 0 -> unbounded (Queue(maxsize=0) is unbounded by design)
    queue_size = 0 if queue_maxsize is None else int(queue_maxsize)
    if queue_size < 0:
        queue_size = 0
    log_queue = Queue(maxsize=queue_size)
    handler = DroppingQueueHandler(log_queue)
    handler._is_app_queue_handler = True
    handler.addFilter(CorrelationIdFilter())
    return log_queue, handler


def _setup_project_logger(
    *,
    logger_name: str,
    level: int,
    queue_handler: DroppingQueueHandler,
) -> logging.Logger:
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(_atexit_shutdown_all)
        _atexit_registered = True

    logger = logging.getLogger(logger_name)

    existing_listener = _active_listeners.pop(logger_name, None)
    if existing_listener:
        _stop_and_close_listener(existing_listener)

    logger.setLevel(level)
    logger.handlers.clear()
    logger.filters.clear()
    logger.propagate = False
    logger.addHandler(queue_handler)
    return logger


def _setup_root_logger(
    *,
    mode: str,
    is_prod: bool,
    level: int,
    queue_handler: DroppingQueueHandler,
) -> None:
    resolved = (mode or "auto").strip().lower()
    if resolved == "auto":
        resolved = "replace" if is_prod else "off"

    # ("add", "replace", "off") are always respected regardless of env.
    if resolved not in {"add", "replace"}:
        return

    root = logging.getLogger()
    if resolved == "replace":
        root.handlers.clear()

    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, "_is_app_queue_handler", False):
            root.removeHandler(handler)
    root.addHandler(queue_handler)


def _resolve_log_path(log_filepath: Union[str, Path]) -> Path:
    """Expand placeholders in a log file path.

    Supported placeholders:
        ``{pid}``  — current process ID (``os.getpid()``)
        ``{hostname}`` — machine hostname

    Example::

        "logs/app.{pid}.log"  →  "logs/app.12345.log"
    """
    resolved = str(log_filepath).format(
        pid=os.getpid(),
        hostname=socket.gethostname(),
    )
    return Path(resolved)


def _build_output_handlers(
    *,
    console_output: bool,
    log_filepath: Optional[Union[str, Path]],
    max_file_size: int,
    backup_count: int,
    webhook_url: Optional[str],
    webhook_timeout: float,
    webhook_level: int,
    webhook_queue_size: int,
) -> list[logging.Handler]:
    handlers: list[logging.Handler] = []

    if console_output:
        handlers.append(logging.StreamHandler(sys.stderr))

    if log_filepath:
        resolved = _resolve_log_path(log_filepath)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                resolved,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
        )

    if webhook_url:
        handlers.append(
            WebhookHandler(
                webhook_url,
                timeout=webhook_timeout,
                level=webhook_level,
                queue_size=webhook_queue_size,
            )
        )

    return handlers


def _create_formatter(
    *,
    json_output: bool,
    is_dev: bool,
) -> logging.Formatter:
    if json_output:
        return JsonFormatter(include_runtime_fields=not is_dev)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s "
        "[cid=%(correlation_id)s] - %(message)s "
        "%(pathname)s:%(lineno)d"
    )
    formatter.converter = time.gmtime
    return formatter


def _start_queue_listener(
    *,
    log_queue: Queue,
    handlers: list[logging.Handler],
    logger_name: str,
) -> QueueListener:
    listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    listener.start()
    _active_listeners[logger_name] = listener
    return listener


def _apply_external_logger_policy(
    *,
    mode: str,
    is_prod: bool,
    logger_name: str,
) -> None:
    resolved = (mode or "auto").strip().lower()
    if resolved == "auto":
        resolved = "propagate" if is_prod else "disable"

    if resolved == "disable":
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.CRITICAL + 1)
        _configure_external_loggers(logger_name=logger_name, mode="disable")
    elif resolved in {"propagate", "keep"}:
        _configure_external_loggers(logger_name=logger_name, mode=resolved)


# ------------------------------------------------------------------ #
#  Public Functions                                                  #
# ------------------------------------------------------------------ #

def configure_logging(
    *,
    log_filepath: Optional[Union[str, Path]] = None,
    max_file_size: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console_output: bool = True,
    json_output: bool = True,
    queue_maxsize: Optional[int] = 10000,
    root_handler_mode: str = "auto",
    external_logger_mode: str = "auto",
    prod_level: int = logging.WARNING,
    webhook_url: Optional[str] = None,
    webhook_timeout: float = 5.0,
    webhook_level: int = logging.ERROR,
    webhook_queue_size: int = 1000,
    logger_name: str = "gLogger",
) -> logging.Logger:
    """Configure centralised, structured logging with queue-based async delivery.

    All log records flow through a ``QueueHandler`` → ``QueueListener``
    pipeline so that the calling thread (or asyncio event loop) is never
    blocked by handler I/O.

    Args:
        log_filepath:
            Path to a rotating log file.  ``None`` disables file output.
            Supports ``{pid}`` and ``{hostname}`` placeholders for
            per-worker files, e.g. ``"logs/app.{pid}.log"``.
        max_file_size:
            Maximum bytes before the log file rotates.  Defaults to 10 MB.
        backup_count:
            Number of rotated backup files to keep.  Defaults to ``5``.
        console_output:
            Emit logs to **stderr**.  Defaults to ``True``.
        json_output:
            Use structured JSON formatting when ``True`` (default), or
            plain-text otherwise.
        queue_maxsize:
            Capacity of the internal log queue.  When full, new records are
            **dropped** (non-blocking) and a warning is written to stderr.
            ``None`` or ``0`` means **unbounded**.  Defaults to ``10 000``.
        root_handler_mode:
            How to treat the **root** logger:

            * ``"auto"`` (default) — ``"replace"`` in prod, ``"off"``
              otherwise.
            * ``"replace"`` — clear existing root handlers, attach queue
              handler.  Honoured in **any** environment.
            * ``"add"`` — keep existing root handlers, append queue handler.
              Honoured in **any** environment.
            * ``"off"`` — leave root untouched.
        external_logger_mode:
            Policy for third-party / framework loggers:

            * ``"auto"`` (default) — ``"propagate"`` in prod (so they go
              through root → queue → your JSON format), ``"disable"``
              everywhere else (only your own ``gLogger.*`` logs appear).
            * ``"disable"`` — silence all non-project loggers.
              Honoured in **any** environment.
            * ``"propagate"`` — force propagation to root.
              Honoured in **any** environment.
            * ``"keep"`` — leave them as-is.
              Honoured in **any** environment.
        prod_level:
            Logging level for the project logger when
            ``APP_ENVIRONMENT=prod``.  Defaults to ``WARNING``.
        webhook_url:
            URL to ``POST`` JSON-formatted records to.  ``None`` disables
            webhook delivery.  Delivery happens in a background thread and
            **never blocks** the caller or the event loop.  Requires the
            ``httpx`` package.
        webhook_timeout:
            HTTP timeout (seconds) for webhook requests.  Defaults to ``5.0``.
        webhook_level:
            Minimum level for records forwarded to the webhook.
            Defaults to ``ERROR``.
        webhook_queue_size:
            Capacity of the webhook delivery queue.  Defaults to ``1000``.
        logger_name:
            Name of the project logger.  Defaults to ``"gLogger"``.
            Child loggers (``"gLogger.mymodule"``) propagate automatically.

    Returns:
        The configured project :class:`~logging.Logger` instance.

    Environment variables:
        ``APP_ENVIRONMENT``:
            Set to ``"prod"`` for production behaviour (project logger at
            *prod_level*, root logger captured, runtime fields in JSON).
            Any other value uses development defaults (``DEBUG`` level,
            external loggers silenced, no runtime fields in JSON).

    Custom level:
        A ``TRACING`` level (numeric **35**, between WARNING and ERROR) is
        registered at import time.  Use ``logger.tracing("msg")`` for
        high-visibility trace points that survive production log-level
        filtering.  All call-sites are easily searchable via
        ``\\.tracing(`` for bulk comment/uncomment.

    Example::

        # application startup (per-worker log file)
        logger = configure_logging(log_filepath="logs/app.{pid}.log")

        # in any module
        log = get_logger("gLogger." + __name__)
        log.info("request handled", extra={"user_id": 42})

        # TRACING – visible in prod (level >= WARNING)
        log.tracing("entered payment flow", extra={"order_id": 99})

        # dev environment with 3rd-party logs visible:
        logger = configure_logging(
            root_handler_mode="replace",
            external_logger_mode="propagate",
        )

        # FastAPI lifespan shutdown
        shutdown_logging()

    ⚠️ Frameworks that re-configure logging
    --------------------------------------
    Some servers/frameworks (e.g. uvicorn, gunicorn, celery) may apply their own
    logging configuration (often via `logging.config.dictConfig()` / `basicConfig()`)
    *after* your code runs. This can clear/replace handlers, change levels/formatters,
    and bypass your queue pipeline (JSON format, correlation IDs, async delivery).

    Common problematic cases:
    - uvicorn started programmatically (it can apply a default log_config)
    - gunicorn (and especially `--preload`, where imports happen in the master process)
    - celery workers (they can hijack the root logger and/or redirect stdout/stderr)

    Typical symptoms:
    - output format suddenly changes (no JSON / different formatter)
    - your logs stop reaching file/webhook
    - framework logs bypass your queue handler/listener

    Mitigations:
    1) Configure after the framework:
        - call `configure_logging()` in app startup/lifespan (or equivalent).

    2) Disable the framework’s logging config when possible:
        - uvicorn programmatic: `uvicorn.run(..., log_config=None)`
        - celery: override/disable its logging setup (e.g. via signals/config).

    3) Re-apply your configuration:
        - call `configure_logging()` again after the framework config runs.

    4) Gunicorn preload:
        - avoid `--preload`, or ensure logging is configured in the worker
        (startup/lifespan or gunicorn worker hooks).
    """
    env = os.getenv("APP_ENVIRONMENT", "").strip().lower()
    is_prod = env == "prod"
    is_dev = env == "dev"

    log_queue, queue_handler = _create_queue_handler(queue_maxsize)

    logger = _setup_project_logger(
        logger_name=logger_name,
        level=prod_level if is_prod else logging.DEBUG,
        queue_handler=queue_handler,
    )

    _setup_root_logger(
        mode=root_handler_mode,
        is_prod=is_prod,
        level=logging.WARNING,
        queue_handler=queue_handler,
    )

    output_handlers = _build_output_handlers(
        console_output=console_output,
        log_filepath=log_filepath,
        max_file_size=max_file_size,
        backup_count=backup_count,
        webhook_url=webhook_url,
        webhook_timeout=webhook_timeout,
        webhook_level=webhook_level,
        webhook_queue_size=webhook_queue_size,
    )

    formatter = _create_formatter(json_output=json_output, is_dev=is_dev)
    for h in output_handlers:
        h.setFormatter(formatter)

    _start_queue_listener(
        log_queue=log_queue,
        handlers=output_handlers,
        logger_name=logger_name,
    )

    _apply_external_logger_policy(
        mode=external_logger_mode,
        is_prod=is_prod,
        logger_name=logger_name,
    )

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger instance by name.

    Example::

        logger = get_logger("gLogger." + __name__)
    """
    return logging.getLogger(name)

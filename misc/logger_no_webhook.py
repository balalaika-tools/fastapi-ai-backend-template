import atexit
import contextlib
import json
import logging
import os
import socket
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from queue import Full, Queue
from typing import Any, ClassVar

# ============================================================
# Custom TRACING level  (between INFO=20 and WARNING=30)
# ============================================================

TRACING = 25
logging.addLevelName(TRACING, "TRACING")


def _tracing(self: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
    """Log a message at the TRACING level (numeric 25).

    Sits just below WARNING so it is included when ``prod_level=TRACING``
    (the default) but filtered out when ``prod_level=WARNING``.
    Easily searchable for bulk comment/uncomment via ``\\.tracing(``.
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

    _cid: ClassVar[ContextVar[str | None]] = ContextVar("correlation_id", default=None)

    @classmethod
    def get(cls) -> str | None:
        return cls._cid.get()

    @classmethod
    def set(cls, cid: str | None) -> Any:
        return cls._cid.set(cid)

    @classmethod
    def reset(cls, token: Any) -> None:
        cls._cid.reset(token)

    @classmethod
    @contextmanager
    def use(cls, cid: str | None) -> Any:
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
    _STANDARD_KEYS = frozenset(
        {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "stack_info",
            "exc_info",
            "exc_text",
            "asctime",
            "correlation_id",
            "taskName",
        }
    )

    def __init__(
        self,
        *,
        include_runtime_fields: bool = True,
        max_value_length: int = 2000,
    ) -> None:
        super().__init__()
        self._include_runtime_fields = include_runtime_fields
        self._max_value_length = max(0, int(max_value_length))
        self._hostname = socket.gethostname()

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    # -- serialization helpers --------------------------------

    def _make_json_serializable(self, obj: Any) -> Any:
        from datetime import date, datetime
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

    def _serialize_value(self, value: Any, _depth: int = 0) -> Any:
        if _depth >= self._MAX_SERIALIZE_DEPTH:
            return self._safe_str(value)
        if isinstance(value, dict):
            return {k: self._serialize_value(v, _depth + 1) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(v, _depth + 1) for v in value]
        return self._make_json_serializable(value)

    def _truncate_value(self, value: str) -> str:
        if self._max_value_length <= 0:
            return value
        if len(value) <= self._max_value_length:
            return value
        return value[: self._max_value_length] + "...(truncated)"

    def _safe_str(self, value: Any) -> str:
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
    _is_app_queue_handler: bool = False

    def __init__(self, queue: Queue[logging.LogRecord]) -> None:
        super().__init__(queue)
        self.dropped_count = 0

    def enqueue(self, record: logging.LogRecord) -> None:
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
# Listener lifecycle
# ============================================================

_active_listeners: dict[str, QueueListener] = {}
_atexit_registered = False


def _stop_and_close_listener(listener: QueueListener | None) -> None:
    if not listener:
        return
    with contextlib.suppress(Exception):
        listener.stop()
    for handler in getattr(listener, "handlers", ()):
        with contextlib.suppress(Exception):
            handler.close()


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


def _create_queue_handler(
    queue_maxsize: int | None,
) -> tuple[Queue[logging.LogRecord], DroppingQueueHandler]:
    # None / 0 -> unbounded (Queue(maxsize=0) is unbounded by design)
    queue_size = 0 if queue_maxsize is None else int(queue_maxsize)
    if queue_size < 0:
        queue_size = 0
    log_queue: Queue[logging.LogRecord] = Queue(maxsize=queue_size)
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
    capture_root: bool,
    level: int,
    queue_handler: DroppingQueueHandler,
) -> None:
    """Attach queue handler to root only when we need to capture external loggers."""
    if not capture_root:
        return
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(queue_handler)


def _resolve_log_path(log_filepath: str | Path) -> Path:
    """Expand placeholders in a log file path.

    Supported placeholders:
        ``{date}``     — today's date as ``YYYY-MM-DD``

    Example::

        "logs/app.{date}.log"  →  "logs/app.2025-06-15.log"
    """
    resolved = str(log_filepath).format(
        date=datetime.now(tz=UTC).strftime("%Y-%m-%d"),
    )
    return Path(resolved)


def _truncate_if_oversized(path: Path, max_size: int) -> None:
    """If *path* exists and exceeds *max_size* bytes, clear it."""
    try:
        if path.exists() and path.stat().st_size > max_size:
            path.write_text("")
    except OSError:
        pass


def _build_output_handlers(
    *,
    console_output: bool,
    log_to_file: bool,
    log_filepath: str | Path,
    max_file_size: int,
) -> list[logging.Handler]:
    handlers: list[logging.Handler] = []

    if console_output:
        handlers.append(logging.StreamHandler(sys.stderr))

    if log_to_file:
        resolved = _resolve_log_path(log_filepath)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        _truncate_if_oversized(resolved, max_file_size)
        handlers.append(logging.FileHandler(resolved, encoding="utf-8"))

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
    log_queue: Queue[logging.LogRecord],
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
    logger_name: str,
) -> None:
    if mode == "disable":
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.CRITICAL + 1)
        _configure_external_loggers(logger_name=logger_name, mode="disable")
    elif mode == "propagate":
        _configure_external_loggers(logger_name=logger_name, mode="propagate")


# ------------------------------------------------------------------ #
#  Public Functions                                                  #
# ------------------------------------------------------------------ #


def configure_logging(
    *,
    external_loggers: str = "disable",
    log_filepath: str | Path = "logs/app.{date}.log",
    max_file_size: int = 15 * 1024 * 1024,
    console_output: bool = True,
    json_output: bool = True,
    queue_maxsize: int | None = 10000,
    prod_level: int = TRACING,
    logger_name: str = "gLogger",
) -> logging.Logger:
    """Configure centralised, structured logging with queue-based async delivery.

    All log records flow through a ``QueueHandler`` → ``QueueListener``
    pipeline so that the calling thread (or asyncio event loop) is never
    blocked by handler I/O.

    Args:
        external_loggers:
            How to handle third-party / framework loggers.  One of:

            * ``"disable"`` *(default)* — silence all non-project loggers.
              Only your own ``gLogger.*`` logs appear.
            * ``"capture"`` — clear their handlers and propagate them through
              root → queue → JSON formatter, so they share the same
              structured output pipeline as your project logs.
            * ``"keep"`` — leave external loggers completely untouched;
              they keep their own handlers and formats.

        log_filepath:
            Path for the log file (only used when ``APP_ENVIRONMENT=local``).
            Supports a ``{date}`` placeholder that expands to today's date
            (``YYYY-MM-DD``).  You can also pass any static or custom path.
            Defaults to ``"logs/app.{date}.log"``.

        max_file_size:
            If the log file already exceeds this size at startup it is
            truncated.  Defaults to 15 MB.  During a single run the file
            may grow beyond this limit.

        console_output:
            Emit logs to **stderr**.  Defaults to ``True``.

        json_output:
            Use structured JSON formatting when ``True`` (default), or
            plain-text otherwise.

        queue_maxsize:
            Capacity of the internal log queue.  When full, new records are
            **dropped** (non-blocking) and a warning is written to stderr.
            ``None`` or ``0`` means **unbounded**.  Defaults to ``10 000``.

        prod_level:
            Logging level for the project logger when
            ``APP_ENVIRONMENT=prod``.  Defaults to ``TRACING`` (25).
            Set to ``logging.WARNING`` to exclude TRACING records in prod.

        logger_name:
            Name of the project logger.  Defaults to ``"gLogger"``.
            Child loggers (``"gLogger.mymodule"``) propagate automatically.

    Returns:
        The configured project :class:`~logging.Logger` instance.

    Environment variables:
        ``APP_ENVIRONMENT``:
            One of ``"local"``, ``"dev"``, ``"stage"``, ``"prod"``.

            * ``"prod"`` — production: project logger at *prod_level*,
              root captured when using ``external_loggers="capture"``.
            * ``"local"`` — same as dev but logs are also written to a file.
            * ``"dev"`` / ``"stage"`` — development defaults (``DEBUG``
              level, no file).

    Custom level:
        A ``TRACING`` level (numeric **25**, between INFO and WARNING) is
        registered at import time.  Use ``logger.tracing("msg")`` for
        high-visibility trace points.  Included by default in prod
        (``prod_level=TRACING``); set ``prod_level=logging.WARNING`` to
        exclude them.  All call-sites are easily searchable via
        ``\\.tracing(``.

    Example::

        # Basic setup — console JSON only (file logging when APP_ENVIRONMENT=local)
        logger = configure_logging()

        # Capture third-party logs through your JSON pipeline
        logger = configure_logging(external_loggers="capture")

        # Custom log file path
        logger = configure_logging(log_filepath="logs/myapp.{date}.log")

        # In any module
        log = get_logger("gLogger." + __name__)
        log.info("request handled", extra={"user_id": 42})
        log.tracing("entered payment flow", extra={"order_id": 99})

        # Shutdown (e.g. FastAPI lifespan)
        shutdown_logging()

    ⚠️ Frameworks that re-configure logging
    ----------------------------------------
    Some servers (uvicorn, gunicorn, celery) may apply their own logging
    config *after* your code runs, clearing handlers or bypassing your
    queue pipeline.

    Mitigations:
      - Call ``configure_logging()`` in app startup/lifespan.
      - Disable framework log config where possible
        (e.g. ``uvicorn.run(..., log_config=None)``).
      - Re-call ``configure_logging()`` after framework config if needed.
    """
    external_loggers = external_loggers.strip().lower()
    if external_loggers not in {"disable", "capture", "keep"}:
        raise ValueError(
            f"external_loggers must be 'disable', 'capture', or 'keep', "
            f"got {external_loggers!r}"
        )

    env = os.getenv("APP_ENVIRONMENT", "").strip().lower()
    is_prod = env == "prod"
    is_dev = env == "dev"
    log_to_file = env == "local"

    # Whether to route the root logger through our queue pipeline.
    # "capture" needs root to funnel external loggers; "disable"/"keep" don't.
    capture_root = external_loggers == "capture"

    log_queue, queue_handler = _create_queue_handler(queue_maxsize)

    logger = _setup_project_logger(
        logger_name=logger_name,
        level=prod_level if is_prod else logging.DEBUG,
        queue_handler=queue_handler,
    )

    _setup_root_logger(
        capture_root=capture_root,
        level=logging.WARNING,
        queue_handler=queue_handler,
    )

    output_handlers = _build_output_handlers(
        console_output=console_output,
        log_to_file=log_to_file,
        log_filepath=log_filepath,
        max_file_size=max_file_size,
    )

    formatter = _create_formatter(json_output=json_output, is_dev=is_dev)
    for h in output_handlers:
        h.setFormatter(formatter)

    _start_queue_listener(
        log_queue=log_queue,
        handlers=output_handlers,
        logger_name=logger_name,
    )

    if external_loggers == "capture":
        _apply_external_logger_policy(mode="propagate", logger_name=logger_name)
    elif external_loggers == "disable":
        _apply_external_logger_policy(mode="disable", logger_name=logger_name)
    # "keep" → do nothing

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger instance by name.

    Example::

        logger = get_logger("gLogger." + __name__)
    """
    return logging.getLogger(name)

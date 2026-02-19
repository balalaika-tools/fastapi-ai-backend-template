import logging

from JustAbackEnd.core.constants import (
    CONSOLE_OUTPUT,
    EXTERNAL_LOGGER_MODE,
    JSON_OUTPUT,
    LOG_FILEPATH,
    LOGGER_NAME,
    MAX_FILE_SIZE,
    PROD_LEVEL,
    QUEUE_MAXSIZE,
    WEBHOOK_LEVEL,
    WEBHOOK_QUEUE_SIZE,
    WEBHOOK_TIMEOUT,
)
from JustAbackEnd.core.logger import configure_logging

# configure_logging expects external_loggers in ("disable", "capture", "keep")
_EXTERNAL_LOGGERS_MAP = {"auto": "disable", "disable": "disable", "capture": "capture", "keep": "keep"}


def setup_logging(webhook_url: str | None) -> logging.Logger:
    external = _EXTERNAL_LOGGERS_MAP.get(
        (EXTERNAL_LOGGER_MODE or "auto").strip().lower(), "disable"
    )
    return configure_logging(
        logger_name=LOGGER_NAME,
        log_filepath=LOG_FILEPATH,
        max_file_size=MAX_FILE_SIZE,
        console_output=CONSOLE_OUTPUT,
        json_output=JSON_OUTPUT,
        queue_maxsize=QUEUE_MAXSIZE,
        external_loggers=external,
        prod_level=PROD_LEVEL,
        webhook_url=webhook_url,
        webhook_timeout=WEBHOOK_TIMEOUT,
        webhook_level=WEBHOOK_LEVEL,
        webhook_queue_size=WEBHOOK_QUEUE_SIZE,
    )

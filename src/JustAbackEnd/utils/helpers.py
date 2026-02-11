import logging

from JustAbackEnd.core.constants import (
    BACKUP_COUNT,
    CONSOLE_OUTPUT,
    EXTERNAL_LOGGER_MODE,
    JSON_OUTPUT,
    LOG_FILEPATH,
    LOGGER_NAME,
    MAX_FILE_SIZE,
    PROD_LEVEL,
    QUEUE_MAXSIZE,
    ROOT_HANDLER_MODE,
    WEBHOOK_LEVEL,
    WEBHOOK_QUEUE_SIZE,
    WEBHOOK_TIMEOUT,
)
from JustAbackEnd.core.logger import configure_logging


def setup_logging(webhook_url: str | None) -> logging.Logger:
    return configure_logging(
        logger_name=LOGGER_NAME,
        log_filepath=LOG_FILEPATH,
        max_file_size=MAX_FILE_SIZE,
        backup_count=BACKUP_COUNT,
        console_output=CONSOLE_OUTPUT,
        json_output=JSON_OUTPUT,
        queue_maxsize=QUEUE_MAXSIZE,
        root_handler_mode=ROOT_HANDLER_MODE,
        external_logger_mode=EXTERNAL_LOGGER_MODE,
        prod_level=PROD_LEVEL,
        webhook_url=webhook_url,
        webhook_timeout=WEBHOOK_TIMEOUT,
        webhook_level=WEBHOOK_LEVEL,
        webhook_queue_size=WEBHOOK_QUEUE_SIZE,
    )

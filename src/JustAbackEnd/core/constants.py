import logging

# ============================================================
# FastAPI Constants
# ============================================================
TITLE = "Template Application"
DESCRIPTION = "A template application for a FastAPI project."
API_VERSION = "1.0.0"
DOCS_URL = "/docs"
REDOC_URL = "/redoc"

# ============================================================
# Server Constants
# ============================================================
LOCAL_DEV_PORT = 6757
HOST = "0.0.0.0"

# ============================================================
# Logging Constants
# ============================================================
MAX_FILE_SIZE = 10 * 1024 * 1024
BACKUP_COUNT = 5
CONSOLE_OUTPUT = True
JSON_OUTPUT = True
QUEUE_MAXSIZE = 10069
ROOT_HANDLER_MODE = "auto"
EXTERNAL_LOGGER_MODE = "auto"
PROD_LEVEL = logging.WARNING
LOGGER_NAME = "gLogger"
LOG_FILEPATH = "Logs/logs.json"
CORRELATION_ID_HEADER = "Request-ID"

# ============================================================
# Webhook Constants
# ============================================================
WEBHOOK_TIMEOUT = 5.0
WEBHOOK_LEVEL = logging.ERROR
WEBHOOK_QUEUE_SIZE = 1000

from contextlib import asynccontextmanager
from fastapi import FastAPI
from JustAbackEnd.utils.helpers import setup_logging
from JustAbackEnd.core.logger import shutdown_logging
from JustAbackEnd.core.settings import get_settings
from JustAbackEnd.core.runtime import AppRuntime
from JustAbackEnd.core.constants import LOGGER_NAME


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Settings first: the logger.info("Settings loaded") inside get_settings()
    # is silently dropped (no handler configured yet). But logger.error() still
    # reaches stderr via Python's lastResort handler — startup failures are visible.
    settings = get_settings()

    webhook = str(settings.webhook_url) if settings.webhook_url else None
    logger = setup_logging(webhook_url=webhook)
    logger.info("🚀 Starting application...")

    runtime = AppRuntime(settings)
    await runtime.init_services()

    app.state.settings = settings
    app.state.runtime = runtime

    logger.info("✅ Application ready")
    try:
        yield
    finally:
        logger.info("🔻 Shutting down...")
        await runtime.close_services()
        shutdown_logging(LOGGER_NAME)

from typing import Optional
from langchain_core.language_models import BaseChatModel
from JustAbackEnd.core.settings import Settings
from JustAbackEnd.ai_engine.model import initialize_model
from JustAbackEnd.core.logger import get_logger
from JustAbackEnd.core.constants import LOGGER_NAME

logger = get_logger(f"{LOGGER_NAME}.{__name__}")


class AppRuntime:
    # Template: Central container for long-lived service instances.
    # Add resources here that must persist for the app's lifetime
    # and need graceful cleanup on shutdown, e.g.:
    #   - httpx.AsyncClient for external API calls
    #   - Database connection pools (asyncpg, SQLAlchemy async)
    #   - Redis clients
    #   - Any client that holds open connections

    def __init__(self, settings: Settings):
        self.settings = settings
        self._model: Optional[BaseChatModel] = None
        # Template: Add more service fields here
        # self._http_client: Optional[httpx.AsyncClient] = None
        # self._db_pool = None

    @property
    def model(self) -> BaseChatModel:
        if self._model is None:
            raise RuntimeError("LLM model not initialized. Call init_services() first.")
        return self._model

    async def init_services(self) -> None:
        logger.info("⚙️  Initializing services...")
        self._model = initialize_model(self.settings)
        # Template: Initialize additional services
        # self._http_client = httpx.AsyncClient(timeout=30)
        logger.info("✅ All services initialized")

    async def close_services(self) -> None:
        logger.info("🔻 Closing services...")
        # Template: Close services in reverse initialization order
        # await self._http_client.aclose()
        # await self._db_pool.close()
        logger.info("✅ All services closed")

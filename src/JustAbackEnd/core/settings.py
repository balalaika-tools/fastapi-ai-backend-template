from functools import lru_cache
from pydantic import Field, SecretStr, HttpUrl
from pydantic_settings import BaseSettings
from typing import Optional
from JustAbackEnd.core.logger import get_logger
from JustAbackEnd.core.constants import LOGGER_NAME

logger = get_logger(f"{LOGGER_NAME}.{__name__}")


class Settings(BaseSettings):

    # ============================================================
    # API Keys
    # ============================================================
    gemini_api_key: SecretStr = Field(..., alias="GEMINI_API_KEY")
    langsmith_api_key: Optional[SecretStr] = Field(default=None, alias="LANGSMITH_API_KEY")

    # ============================================================
    # LangSmith Configuration
    # ============================================================
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_project: str = Field(default="default", alias="LANGSMITH_PROJECT")

    # ============================================================
    # Model Configuration
    # ============================================================
    model_name: str = Field(default="google_genai:gemini-2.5-flash", alias="MODEL_NAME")
    temperature: float = Field(default=0, alias="TEMPERATURE")

    # ============================================================
    # Webhook Configuration
    # ============================================================
    webhook_url: Optional[HttpUrl] = Field(default=None, alias="WEBHOOK_URL")

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "populate_by_name": True,
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as e:
        logger.error(f"❌ Failed to load settings: {e}")
        raise

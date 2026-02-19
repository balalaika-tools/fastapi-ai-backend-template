from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings

from JustAbackEnd.core.constants import LOGGER_NAME
from JustAbackEnd.core.logger import get_logger

logger = get_logger(f"{LOGGER_NAME}.{__name__}")

AppEnvironment = Literal["local", "dev", "stage", "prod"]


class Settings(BaseSettings):
    # ============================================================
    # App environment (local | dev | stage | prod)
    # ============================================================
    app_environment: AppEnvironment = Field(default="local", alias="APP_ENVIRONMENT")

    # ============================================================
    # API Keys
    # ============================================================
    gemini_api_key: SecretStr = Field(..., alias="GEMINI_API_KEY")
    langsmith_api_key: SecretStr | None = Field(default=None, alias="LANGSMITH_API_KEY")

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
    webhook_url: HttpUrl | None = Field(default=None, alias="WEBHOOK_URL")

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "populate_by_name": True,
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as e:
        logger.error(f"❌ Failed to load settings: {e}")
        raise

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from JustAbackEnd.api.exceptions import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from JustAbackEnd.api.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
)
from JustAbackEnd.api.routers.health import router as health_router
from JustAbackEnd.api.routers.llm import router as llm_router
from JustAbackEnd.bootstrap.lifespan import lifespan
from JustAbackEnd.core.constants import (
    API_VERSION,
    DESCRIPTION,
    DOCS_URL,
    LOGGER_NAME,
    REDOC_URL,
    TITLE,
)
from JustAbackEnd.core.logger import get_logger

logger = get_logger(f"{LOGGER_NAME}.{__name__}")


def _setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        HTTPException,
        http_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(Exception, general_exception_handler)


def _setup_middleware(app: FastAPI) -> None:
    # Template: Configure CORS origins for production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)


def _setup_routers(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(llm_router)


def create_app() -> FastAPI:
    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        version=API_VERSION,
        lifespan=lifespan,
        default_response_class=ORJSONResponse,
        docs_url=DOCS_URL,
        redoc_url=REDOC_URL,
    )
    _setup_exception_handlers(app)
    _setup_middleware(app)
    _setup_routers(app)
    logger.info("🏗️  FastAPI app configured")
    return app

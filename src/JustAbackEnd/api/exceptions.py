from fastapi import Request, HTTPException, status
from fastapi.responses import ORJSONResponse
from fastapi.exceptions import RequestValidationError
from JustAbackEnd.core.logger import get_logger
from JustAbackEnd.core.constants import LOGGER_NAME

logger = get_logger(f"{LOGGER_NAME}.{__name__}")


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> ORJSONResponse:
    errors = exc.errors()
    detail = ", ".join(f"{e['loc']}: {e['msg']}" for e in errors)
    logger.warning(f"⚠️  Validation error on {request.url.path}: {detail}")
    return ORJSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "validation_error", "message": "Invalid request parameters", "detail": errors},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> ORJSONResponse:
    if exc.status_code >= 500:
        logger.error(f"❌ HTTP {exc.status_code} on {request.url.path}: {exc.detail}")
    return ORJSONResponse(
        status_code=exc.status_code,
        content={"error": f"http_{exc.status_code}", "message": str(exc.detail), "detail": None},
    )


async def general_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    logger.error(f"💥 Unhandled {type(exc).__name__} on {request.url.path}: {exc}", exc_info=True)
    return ORJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_server_error", "message": "An unexpected error occurred", "detail": None},
    )

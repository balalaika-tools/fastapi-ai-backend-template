from fastapi import APIRouter, Depends
from fastapi.responses import ORJSONResponse

from JustAbackEnd.api.dependencies import get_app_runtime
from JustAbackEnd.api.schemas import ChatCompletionRequest, ChatCompletionResponse
from JustAbackEnd.core.constants import LOGGER_NAME
from JustAbackEnd.core.logger import get_logger
from JustAbackEnd.core.runtime import AppRuntime
from JustAbackEnd.services.llm_service import chat_completion

logger = get_logger(f"{LOGGER_NAME}.{__name__}")

router = APIRouter(prefix="/api/v1", tags=["LLM"])


@router.post(
    "/chat", response_model=ChatCompletionResponse, response_class=ORJSONResponse
)
async def chat_endpoint(
    body: ChatCompletionRequest,
    runtime: AppRuntime = Depends(get_app_runtime),  # noqa: B008
) -> ChatCompletionResponse:
    logger.info(f"🤖 Chat request | session={body.session_id}")
    result = await chat_completion(runtime.model, body)
    logger.info(f"✅ Chat response sent | session={body.session_id}")
    return result

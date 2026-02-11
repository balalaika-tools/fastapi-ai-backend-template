from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from JustAbackEnd.ai_engine.prompts import SYSTEM_PROMPT
from JustAbackEnd.api.schemas import ChatCompletionRequest, ChatCompletionResponse
from JustAbackEnd.core.constants import LOGGER_NAME
from JustAbackEnd.core.logger import get_logger

logger = get_logger(f"{LOGGER_NAME}.{__name__}")


async def chat_completion(
    model: BaseChatModel, request: ChatCompletionRequest
) -> ChatCompletionResponse:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=request.prompt),
    ]
    response = await model.ainvoke(messages)
    content = response.content
    response_str = content if isinstance(content, str) else str(content)
    return ChatCompletionResponse(
        response=response_str,
        session_id=request.session_id,
    )

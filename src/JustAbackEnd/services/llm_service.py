from langchain_core.messages import HumanMessage, SystemMessage
from JustAbackEnd.api.schemas import ChatCompletionRequest, ChatCompletionResponse
from JustAbackEnd.ai_engine.prompts import SYSTEM_PROMPT
from JustAbackEnd.core.logger import get_logger
from JustAbackEnd.core.constants import LOGGER_NAME

logger = get_logger(f"{LOGGER_NAME}.{__name__}")


async def chat_completion(model, request: ChatCompletionRequest) -> ChatCompletionResponse:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=request.prompt),
    ]
    response = await model.ainvoke(messages)
    return ChatCompletionResponse(
        response=response.content,
        session_id=request.session_id,
    )

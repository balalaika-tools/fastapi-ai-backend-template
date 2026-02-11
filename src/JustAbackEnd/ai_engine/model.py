from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from JustAbackEnd.core.settings import Settings


def initialize_model(settings: Settings) -> BaseChatModel:
    return init_chat_model(settings.model_name, temperature=settings.temperature)

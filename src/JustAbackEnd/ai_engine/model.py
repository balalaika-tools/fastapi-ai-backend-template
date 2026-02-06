from langchain.chat_models import init_chat_model
from JustAbackEnd.core.settings import Settings


def initialize_model(settings: Settings):
    return init_chat_model(settings.model_name, temperature=settings.temperature)

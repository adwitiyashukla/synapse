from app.config import get_settings
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAIProvider

_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        _provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            embedding_model=settings.embedding_model,
        )
    return _provider


def set_provider(provider: LLMProvider | None) -> None:
    global _provider
    _provider = provider

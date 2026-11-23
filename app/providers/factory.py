from app.config import Settings, get_settings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import LLMProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


class LLMConfigError(RuntimeError):
    pass


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    s = settings or get_settings()
    model = (s.llm_model or "").strip()
    if not model:
        raise LLMConfigError(
            "LLM_MODEL is not set. Set it in .env to a model name your provider accepts "
            "(for example gpt-4o-mini, llama3.1, or claude-haiku-4-5)."
        )
    if s.llm_provider == "anthropic":
        return AnthropicProvider(
            api_key=s.llm_key,
            model=model,
            timeout=s.llm_timeout_s,
            max_tokens=s.llm_max_tokens,
        )
    if s.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider(
            api_key=s.llm_key,
            model=model,
            base_url=s.llm_base_url,
            json_mode=s.llm_json_mode,
            disable_thinking=s.llm_disable_thinking,
            reasoning_effort=s.llm_reasoning_effort,
            timeout=s.llm_timeout_s,
            max_tokens=s.llm_max_tokens,
        )
    raise LLMConfigError(f"Unknown LLM_PROVIDER: {s.llm_provider}")

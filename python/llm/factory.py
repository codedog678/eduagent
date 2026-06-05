"""
LLM 工厂函数。

根据配置自动选择合适的 LLM 提供者。
"""

from config.settings import settings
from llm.base import BaseLLM


def get_llm() -> BaseLLM:
    """
    根据配置返回对应的 LLM 实例。

    优先级: Anthropic > OpenAI > MiniMax > DeepSeek > Template

    Returns:
        BaseLLM 实例
    """
    provider = settings.configured_llm_provider

    if provider == "anthropic":
        from llm.anthropic_adapter import AnthropicLLM

        return AnthropicLLM(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
            model=settings.model_id,
        )

    if provider == "openai":
        from llm.openai_adapter import OpenAILLM

        return OpenAILLM(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
        )

    if provider == "minimax":
        from llm.minimax_adapter import MiniMaxLLM

        return MiniMaxLLM(
            api_key=settings.minimax_api_key,
            model=settings.minimax_model,
        )

    if provider == "deepseek":
        from llm.deepseek_adapter import DeepSeekLLM

        return DeepSeekLLM(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
        )

    from llm.template_adapter import TemplateLLM

    return TemplateLLM()

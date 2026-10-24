"""
LLM 工厂函数。

根据配置自动选择合适的 LLM 提供者。
"""

from config.settings import settings
from llm.base import BaseLLM


def get_llm() -> BaseLLM:
    """
    根据配置返回对应的 LLM 实例。

    显式 LLM_PROVIDER 优先；auto 时按已配置的 Key 选择。

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
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            thinking=settings.deepseek_thinking,
            reasoning_effort=settings.deepseek_reasoning_effort,
        )

    from llm.template_adapter import TemplateLLM

    return TemplateLLM()

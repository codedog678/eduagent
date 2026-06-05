"""
外部交互层。

封装 LLM 对话管理、多轮对话、主动引导等功能。
"""

from interaction.dialog_manager import DialogManager
from interaction.proactive_guide import ProactiveGuide
from interaction.context_manager import ContextManager

__all__ = ["DialogManager", "ProactiveGuide", "ContextManager"]

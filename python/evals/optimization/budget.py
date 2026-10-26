"""任务、裁判、反思共用总账；保留原执行器的每例/每批预算。"""

from dataclasses import dataclass
import math

from core.run_context import RunExhausted
from evals.live_budget import LiveBudget


class OptimizationStopped(RuntimeError):
    """预算/基础设施问题停止优化，不能作为任务负例参与候选选择。"""


@dataclass
class OptimizationBudget(LiveBudget):
    blocked: bool = False

    def __post_init__(self):
        if (not isinstance(self.max_requests, int) or self.max_requests <= 0
                or not math.isfinite(self.max_cny) or self.max_cny <= 0):
            raise ValueError("positive finite total request and CNY caps are required")

    def reserve_for(self, role, messages, tools, max_tokens):
        try:
            index = super().reserve(messages, tools, max_tokens)
        except RunExhausted:
            self.blocked = True
            raise OptimizationStopped("global model request or estimated CNY budget exhausted") from None
        self.ledger[index]["role"] = role
        return index

    def require_requests(self, count):
        if self.blocked or self.requests + count > self.max_requests:
            raise OptimizationStopped("insufficient requests to complete the next evaluation batch")

    def summary(self):
        result = super().summary()
        result["roles"] = {
            role: sum(row.get("role") == role for row in self.ledger)
            for role in ("task", "judge", "reflection")
        }
        return result


class TextModel:
    """复用已配置 DeepSeek 客户端；纯文本请求不传空工具，不启用 SDK 重试。"""

    def __init__(self, service, budget):
        self.service, self.budget = service, budget

    async def complete(self, messages, *, role, max_tokens=2200):
        index = self.budget.reserve_for(role, messages, [], max_tokens)
        try:
            response = await self.service._get_client().chat.completions.create(
                model=self.service.model, messages=messages, max_tokens=max_tokens,
                response_format={"type": "json_object"},
                **self.service._compatible_request_options(temperature=0),
            )
        except Exception as exc:
            # 原始异常可能含请求正文或服务地址；日志只记录类型。
            raise OptimizationStopped(f"{role} request failed: {type(exc).__name__}") from None
        usage = response.usage
        if usage:
            normalized = {"input_tokens": usage.prompt_tokens,
                          "output_tokens": usage.completion_tokens}
            hit = getattr(usage, "prompt_cache_hit_tokens", None)
            if isinstance(hit, int):
                normalized["prompt_cache_hit_tokens"] = hit
            self.budget.settle(index, normalized)
        choice = response.choices[0]
        if choice.finish_reason != "stop" or not choice.message.content:
            raise OptimizationStopped(f"{role} response incomplete")
        return choice.message.content

"""真实评测的请求上限和 DeepSeek Flash 费用估算，不读取凭据。"""

from dataclasses import dataclass, field
import json

from core.run_context import RunExhausted


PRICING = {
    "source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
    "verified_date": "2026-10-25",
    "currency": "CNY",
    "per_million_tokens": {
        "peak": {"input_miss": 2.0, "input_hit": 0.04, "output": 8.0},
        "off_peak": {"input_miss": 1.0, "input_hit": 0.02, "output": 4.0},
    },
}


PRO_PRICING = {
    **PRICING, "verified_date": "2026-10-29", "model": "deepseek-v4-pro",
    "per_million_tokens": {
        "peak": {"input_miss": 9.0, "input_hit": 0.30, "output": 27.0},
        "off_peak": {"input_miss": 4.5, "input_hit": 0.15, "output": 13.5},
    },
}


def cost_estimate(usage: dict, period: str = "peak", pricing=None) -> float:
    rates = (pricing or PRICING)["per_million_tokens"][period]
    total = usage.get("input_tokens", 0)
    hit = min(total, usage.get("prompt_cache_hit_tokens", 0))
    # 缺少供应商缓存字段时按未命中计价。
    return ((total - hit) * rates["input_miss"] + hit * rates["input_hit"]
            + usage.get("output_tokens", 0) * rates["output"]) / 1_000_000


@dataclass
class LiveBudget:
    max_requests: int = 42
    max_cny: float = 3.0
    requests: int = 0
    estimated_peak_cny: float = 0.0
    estimated_off_peak_cny: float = 0.0
    unconfirmed_reservation_cny: float = 0.0
    ledger: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not 0 < self.max_requests <= 42 or not 0 < self.max_cny <= 3:
            raise ValueError("live batch caps must be <=42 requests and <=3 CNY")

    def reserve(self, messages: list, tools: list, max_tokens: int, *, pricing=None) -> int:
        # UTF-8 字节数加协议余量作为保守输入上界；不是供应商精确 Token 数。
        input_bound = len(json.dumps(
            {"messages": messages, "tools": tools}, ensure_ascii=False
        ).encode("utf-8")) + 1024
        reserved = cost_estimate({"input_tokens": input_bound, "output_tokens": max_tokens},
                                 pricing=pricing)
        if self.requests >= self.max_requests:
            raise RunExhausted("live_request_budget")
        if self.estimated_peak_cny + self.unconfirmed_reservation_cny + reserved > self.max_cny:
            raise RunExhausted("live_cost_budget")
        self.requests += 1
        self.unconfirmed_reservation_cny += reserved
        self.ledger.append({"request_no": self.requests, "reservation_cny": reserved,
                            "usage": None, "status": "unconfirmed"})
        if pricing:
            self.ledger[-1]["pricing"] = pricing
        return len(self.ledger) - 1

    def settle(self, index: int, usage: dict):
        record = self.ledger[index]
        if record["status"] != "unconfirmed":
            raise ValueError("request already settled")
        if not {"input_tokens", "output_tokens"} <= usage.keys():
            return
        if any(not isinstance(value, int) or value < 0 for value in usage.values()):
            raise ValueError("invalid provider usage")
        self.unconfirmed_reservation_cny -= record["reservation_cny"]
        record.update(usage=usage, status="usage_recorded",
                      estimated_peak_cny=cost_estimate(usage, pricing=record.get("pricing")),
                      estimated_off_peak_cny=cost_estimate(usage, "off_peak",
                                                         pricing=record.get("pricing")))
        self.estimated_peak_cny += record["estimated_peak_cny"]
        self.estimated_off_peak_cny += record["estimated_off_peak_cny"]

    @property
    def exhausted(self) -> bool:
        return (self.requests >= self.max_requests
                or self.estimated_peak_cny + self.unconfirmed_reservation_cny >= self.max_cny)

    def summary(self) -> dict:
        usage = {}
        for entry in self.ledger:
            for key, value in (entry["usage"] or {}).items():
                usage[key] = usage.get(key, 0) + value
        return {
            "max_requests": self.max_requests, "max_cny": self.max_cny,
            "requests": self.requests, "usage": usage,
            "estimated_peak_cny": self.estimated_peak_cny,
            "estimated_off_peak_cny": self.estimated_off_peak_cny,
            "unconfirmed_reservation_cny": max(0, self.unconfirmed_reservation_cny),
            "billing_status": "estimate_only",
            "pricing": PRICING,
            "pricing_note": "Default Flash rates; per-request pricing overrides apply when present.",
        }

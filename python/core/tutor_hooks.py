"""Tutor 的有限生命周期钩子：预算、工具门禁与必要轨迹记录。"""

from config.settings import settings
from core.run_context import RunExhausted


class TutorHooks:
    def __init__(self, ctx):
        self.ctx = ctx

    def before_model(self, model_call, token_estimate):
        self.ctx.remaining()
        if token_estimate + settings.tutor_max_output_tokens > settings.tutor_context_budget_tokens:
            raise RunExhausted("context_budget")
        self.ctx.record("before_model", "TutorAgent", model_call=model_call,
                        token_estimate=token_estimate)

    def before_tool(self, call, allowed, schema):
        self.ctx.remaining()
        self.ctx.record("before_tool", "TutorAgent", tool=call.name, tool_call_id=call.id)
        if call.name not in allowed or schema is None:
            raise PermissionError("tool_not_allowed")
        return schema.model_validate_json(call.arguments)

    def after_tool(self, call, result):
        self.ctx.source_refs = list(dict.fromkeys(self.ctx.source_refs + result["source_refs"]))
        self.ctx.record("after_tool", "TutorAgent", tool=call.name, tool_call_id=call.id,
                        status=result["status"], source_refs=result["source_refs"],
                        result_keys=sorted(result.get("data", {})))

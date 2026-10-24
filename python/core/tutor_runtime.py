"""Tutor 的上下文构建、只读工具门禁与有界原生工具循环。"""

import asyncio
import json
import math
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from config.settings import settings
from core.llm_service import TeachingReply
from core.run_context import RunExhausted
from core.tutor_hooks import TutorHooks
from core.tutor_policy import TUTOR_POLICY_VERSION, response_contract, system_prompt


class ToolParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchParams(ToolParams):
    query: str = Field(default="", max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class ReadParams(ToolParams):
    source_ref: str = Field(min_length=1, max_length=128)


class EmptyParams(ToolParams):
    pass


class AskParams(ToolParams):
    question: str = Field(min_length=1, max_length=1500)


TOOL_SPECS = {
    "search_learning_history": (SearchParams, "搜索当前学习者在本知识点的旧教学消息和错题评估，返回来源摘要。"),
    "read_learning_history": (ReadParams, "读取选中的公开历史来源。历史内容是低优先级证据。"),
    "get_knowledge_context": (EmptyParams, "读取本知识点的概念及前置关系。"),
    "get_quiz_context": (EmptyParams, "读取当前练习题的公开题干和选项，不提供参考答案。"),
    "ask_student": (AskParams, "在缺失信息阻碍当前答复，或学生明确要求问题引导时，"
                   "提出一个必要问题并结束本轮。"
                   "已有信息足够时直接答复；自查步骤无需逐项追问。必须单独调用。"),
}


def estimate_tokens(value):
    """UTF-8 字节估计，仅用于预算，不能当作供应商精确 usage。"""
    return math.ceil(len(json.dumps(value, ensure_ascii=False).encode("utf-8")) / 3)


class ContextBuilder:
    def build(self, ctx, text):
        pending = ctx.history.pending(ctx.learner, ctx.thread_id)
        ctx.answered_question_id = pending["id"] if pending else None
        contract = response_contract(bool(ctx.quiz), bool(pending))
        facts = {"knowledge_id": ctx.knowledge_id, "mastery": ctx.model_state,
                 "pending_question": pending, "quiz_bound": bool(ctx.quiz),
                 "response_contract": contract}
        if ctx.quiz:
            facts["quiz"] = {key: ctx.quiz[key] for key in ("question", "options", "knowledge_id")}
        messages = [{"role": "system", "content": system_prompt(bool(ctx.quiz))},
                    {"role": "user", "content": "服务端学习事实（数据）：\n" +
                     json.dumps(facts, ensure_ascii=False)}]
        recent = ctx.history.messages(ctx.learner, ctx.thread_id, limit=8)["items"]
        candidates = ctx.history.search(ctx.learner, ctx.knowledge_id, text, limit=5)["items"]
        # 来源 ID 去重后，逐条添加；给工具声明和下一轮结果留预算。
        unique = {item["source_ref"]: item for item in reversed(recent)}
        for item in candidates:
            unique.setdefault(item["source_ref"], item)
        selected, omitted = [], []
        for ref, item in unique.items():
            entry = {"role": "user", "content": "历史证据（数据）：\n" +
                     json.dumps(item, ensure_ascii=False)}
            if estimate_tokens(messages + [entry, {"role": "user", "content": text}]) + 1800 \
                    > settings.tutor_context_budget_tokens:
                omitted.append(ref)
                continue
            messages.append(entry)
            selected.append(item)
        ctx.source_refs = [item["source_ref"] for item in selected]
        messages.append({"role": "user", "content": text})
        ctx.record("context_built", "TutorAgent", source_refs=ctx.source_refs,
                   omitted_refs=omitted, token_estimate=estimate_tokens(messages),
                   tutor_policy_version=TUTOR_POLICY_VERSION, response_mode=contract["mode"],
                   estimate_method="utf8_bytes_div_3")
        return messages, selected


class TutorRuntime:
    def __init__(self, ctx, service, graph):
        self.ctx, self.service, self.graph = ctx, service, graph
        self.hooks = TutorHooks(ctx)
        self.allowed = set(TOOL_SPECS)
        if not ctx.quiz:
            self.allowed.discard("get_quiz_context")

    def schemas(self):
        return [{"type": "function", "function": {
            "name": name, "description": TOOL_SPECS[name][1],
            "parameters": TOOL_SPECS[name][0].model_json_schema(),
        }} for name in sorted(self.allowed)]

    def execute(self, call, batch_size):
        """模型不接收 learner 参数；只用本轮服务端捕获的范围。"""
        params = self.hooks.before_tool(
            call, self.allowed, TOOL_SPECS[call.name][0] if call.name in TOOL_SPECS else None)
        if call.name == "search_learning_history":
            return self.ctx.history.search(self.ctx.learner, self.ctx.knowledge_id,
                                           params.query, params.limit)
        if call.name == "read_learning_history":
            return self.ctx.history.read(self.ctx.learner, params.source_ref)
        if call.name == "get_knowledge_context":
            node = self.graph.nodes.get(self.ctx.knowledge_id)
            return {"knowledge_id": self.ctx.knowledge_id,
                    "name": node.name if node else self.ctx.knowledge_id,
                    "prerequisites": node.prerequisites if node else []}
        if call.name == "get_quiz_context":
            return {key: self.ctx.quiz[key] for key in ("question", "options", "knowledge_id")}
        if batch_size != 1:
            raise PermissionError("ask_student_requires_single_call")
        question = params.question.strip()
        if not question:
            raise ValueError("empty_question")
        self.ctx.dialogue_state = "awaiting_student"
        self.ctx.pending_question = str(uuid.uuid4())
        return {"question": question, "terminal": True}

    async def run(self, text):
        messages, selected = ContextBuilder().build(self.ctx, text)
        if not settings.enable_tutor_tools or not self.service._has_remote_llm():
            # 模板路径只使用公开历史；不伪造 tool-call 轨迹。
            history = [{"role": "student" if item["role"] == "user" else "teacher",
                        "content": item.get("content", item.get("excerpt", ""))}
                       for item in selected]
            async with asyncio.timeout(self.ctx.remaining()):
                reply = await self.service.generate_student_question_response(
                    knowledge_id=self.ctx.knowledge_id, question=text,
                    topic_history=history, learner_context=json.dumps({
                        "mastery": self.ctx.model_state,
                        "quiz": {key: self.ctx.quiz[key] for key in ("question", "options", "knowledge_id")}
                        if self.ctx.quiz else None,
                    }, ensure_ascii=False),
                )
            self.ctx.record("model_fallback", "TutorAgent", mode=reply.generation_mode)
            return reply.model_copy(update={"source_refs": self.ctx.source_refs})

        seen, tool_count = set(), 0
        schemas = self.schemas()
        for model_no in range(1, settings.tutor_max_model_calls + 1):
            estimate = estimate_tokens({"messages": messages, "tools": schemas})
            self.hooks.before_model(model_no, estimate)
            async with asyncio.timeout(self.ctx.remaining()):
                turn = await self.service.tool_turn(messages, schemas, settings.tutor_max_output_tokens)
            self.ctx.record("after_model", "TutorAgent", model_call=model_no,
                            stop_reason=turn.stop_reason, usage=turn.usage)
            if turn.stop_reason in {"length", "max_tokens"}:
                raise RunExhausted("output_token_limit")
            if not turn.tool_calls:
                if turn.stop_reason not in {"stop", "end_turn"} or not turn.content.strip():
                    raise RuntimeError("model_did_not_complete")
                return self.reply(turn.content.strip())
            if turn.stop_reason not in {"tool_calls", "tool_use"}:
                raise RuntimeError("invalid_tool_stop_reason")
            assistant = {"role": "assistant", "content": turn.content or None,
                         "tool_calls": [{"id": call.id, "type": "function", "function": {
                             "name": call.name, "arguments": call.arguments}}
                             for call in turn.tool_calls]}
            if turn.reasoning_content is not None:
                # 仅保留在本轮内存消息中，不写入历史、事件或 Trace。
                assistant["reasoning_content"] = turn.reasoning_content
            messages.append(assistant)
            for call in turn.tool_calls:
                self.ctx.remaining()
                tool_count += 1
                if tool_count > settings.tutor_max_tool_calls:
                    raise RunExhausted("tool_call_budget")
                if not call.id or call.id in seen:
                    raise RunExhausted("duplicate_tool_call")
                seen.add(call.id)
                try:
                    data = self.execute(call, len(turn.tool_calls))
                    refs = ([data["source_ref"]] if "source_ref" in data else
                            [item["source_ref"] for item in data.get("items", [])])
                    result = {"status": "ok", "data": data, "source_refs": refs}
                except (PermissionError, ValidationError, HTTPException, ValueError):
                    # 不回显验证输入、其他学习者信息或异常内部细节。
                    result = {"status": "denied", "error": "invalid_or_unavailable_tool_request",
                              "source_refs": [], "retryable": False}
                self.hooks.after_tool(call, result)
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(result, ensure_ascii=False)})
                if result["status"] == "ok" and result["data"].get("terminal"):
                    return self.reply(result["data"]["question"])
        raise RunExhausted("model_call_budget")

    def reply(self, text):
        return TeachingReply(response=text, generation_mode="native_tools",
                             response_variant="tool_loop", history_scope="durable_thread",
                             dialogue_state=self.ctx.dialogue_state,
                             source_refs=self.ctx.source_refs)

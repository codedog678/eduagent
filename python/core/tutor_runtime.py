"""Tutor 的上下文构建、只读工具门禁与有界原生工具循环。"""

import asyncio
import json
import math
import re

from config.settings import settings
from core.llm_service import TeachingReply
from core.run_context import RunExhausted
from core.tutor_hooks import TutorHooks
from core.tool_executor import REGISTRY, ToolExecutor
from core.tutor_policy import TUTOR_POLICY_VERSION, response_contract, system_prompt


# 保留旧评测入口的五工具契约；新增工具声明与执行以共享注册表为准。
TOOL_SPECS = {name: (spec.schema, spec.description) for name, spec in REGISTRY.items()
              if name in {"search_learning_history", "read_learning_history", "get_knowledge_context",
                          "get_quiz_context", "ask_student"}}

MEMORY_WRITE_RULES = (
    "\n记忆确认规则：memory_write_state 是服务端提供的本轮写入状态。"
    "pending_commit 表示原话已接受，将与本轮回复一起保存；只有提交成功，学生才会收到回复。"
    "已接受的相同内容无需重复调用保存工具。之后一次工具参数错误不会撤销先前接受的提案，"
    "不能据此声称整轮保存失败、只能在当前会话记住或让学生重复提醒。"
    "确认时用自然语言说明会按已接受的偏好执行，不向学生报告内部工具或事务细节。"
    "学生只要求记住并简单确认时，仅简短确认，不额外开始讲解或练习。"
    "requires_confirmation=true 表示偏好冲突尚未解决，应说明需要确认，不能声称已替代旧偏好。"
    "not_staged 时不能声称已保存。"
)


def estimate_tokens(value):
    """UTF-8 字节估计，仅用于预算，不能当作供应商精确 usage。"""
    return math.ceil(len(json.dumps(value, ensure_ascii=False).encode("utf-8")) / 3)


def plan_context(ctx):
    if not ctx.plan:
        return None
    # 专家结果单独传递，避免持久化收据与结果在提示中重复占用预算。
    return {key: ctx.plan.get(key) for key in (
        "goal", "constraints", "steps", "student_inputs", "checks", "practice_quiz_id")}


class ContextBuilder:
    def build(self, ctx, text):
        pending = ctx.history.pending(ctx.learner, ctx.thread_id)
        ctx.answered_question_id = pending["id"] if pending else None
        contract = response_contract(bool(ctx.quiz), bool(pending))
        facts = {"knowledge_id": ctx.knowledge_id, "mastery": ctx.model_state,
                 "pending_question": pending, "quiz_bound": bool(ctx.quiz),
                 "response_contract": contract,
                 "stable_memories": ctx.history.memory.profile(ctx.learner),
                 "staged_memories": ctx.memory_proposals,
                 "memory_write_state": ctx.history.memory.write_state(ctx),
                 "learning_plan": plan_context(ctx),
                 "expert_proposals": ctx.expert_results}
        if ctx.quiz:
            facts["quiz"] = {key: ctx.quiz[key] for key in ("question", "options", "knowledge_id")}
        messages = [{"role": "system", "content": system_prompt(bool(ctx.quiz))},
                    {"role": "user", "content": "服务端学习事实（数据）：\n" +
                     json.dumps(facts, ensure_ascii=False)}]
        if ctx.plan:
            messages[0]["content"] += (
                "\n按计划中的原始目标、约束和学生补充信息接续任务。"
                "检查步骤状态及动作收据：失败或阻塞的工作须说明缺口，不能声称完整完成。"
                "只有已成功准备的练习才能说已准备好；发出练习不代表学生已掌握。")
        if ctx.memory_proposals:
            messages[0]["content"] += MEMORY_WRITE_RULES
        recent = ctx.history.messages(ctx.learner, ctx.thread_id, limit=8)["items"]
        candidates = (ctx.retrieved_items if ctx.retrieved_items is not None else
                      ctx.history.search(ctx.learner, ctx.knowledge_id, text, limit=5)["items"])
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
        ctx.source_refs = list(dict.fromkeys(ctx.source_refs + [item["source_ref"] for item in selected]
                                            + [item["source_ref"] for item in facts["stable_memories"]]))
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
        self.executor = ToolExecutor(ctx, graph, "Tutor")

    def schemas(self):
        return self.executor.schemas()

    async def execute(self, call, batch_size=1):
        return await self.executor.execute(call, batch_size)

    async def run(self, text):
        self.ctx.role = "Tutor"
        if self.ctx.prepared_quiz:
            quiz_id, quiz = self.ctx.prepared_quiz
            # 专家准备后又经过 Tutor 辅导的题目按受助练习记账。
            quiz["assisted"] = True
            self.ctx.quiz = {**quiz, "quiz_id": quiz_id}
        self.ctx.retrieved_items = (await self.ctx.history.retrieval.search(
            self.ctx.learner, self.ctx.knowledge_id, text, 5, self.ctx))["items"]
        self.ctx.retrieved_refs = list(dict.fromkeys(self.ctx.retrieved_refs +
            [item["source_ref"] for item in self.ctx.retrieved_items]))
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
                        "learning_plan": plan_context(self.ctx),
                        "expert_proposals": self.ctx.expert_results,
                        "stable_memories": self.ctx.history.memory.profile(self.ctx.learner),
                        "memory_write_state": self.ctx.history.memory.write_state(self.ctx),
                        "memory_confirmation_rules": MEMORY_WRITE_RULES if self.ctx.memory_proposals else "",
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
            # 工具返回原文后释放旧历史块，为新证据留空间；当前输入/待答/工具协议不丢弃。
            while estimate + settings.tutor_max_output_tokens > settings.tutor_context_budget_tokens:
                removable = next((i for i, m in enumerate(messages)
                                  if m["role"] == "user" and
                                  m.get("content", "").startswith("历史证据（数据）：\n")), None)
                if removable is None:
                    break
                messages.pop(removable)
                self.ctx.record("context_compacted", "TutorAgent", reason="make_room_for_tool_evidence")
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
                result = await self.executor.execute(call, len(turn.tool_calls))
                if call.name == "propose_memory_update" and MEMORY_WRITE_RULES not in messages[0]["content"]:
                    messages[0]["content"] += MEMORY_WRITE_RULES
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(result, ensure_ascii=False)})
                if result["status"] == "ok" and result["data"].get("terminal"):
                    return self.reply(result["data"]["question"])
        raise RunExhausted("model_call_budget")

    def reply(self, text):
        cited = list(dict.fromkeys(re.findall(r"(?:message|evidence|memory):[A-Za-z0-9_-]+", text)))
        if any(ref not in self.ctx.source_refs or not self.ctx.history.memory.source(self.ctx.learner, ref)
               for ref in cited):
            raise ValueError("unverified_final_citation")
        self.ctx.cited_refs = cited
        self.ctx.record("response_sources", "TutorAgent", retrieved_refs=self.ctx.retrieved_refs,
                        read_refs=self.ctx.read_refs, cited_refs=cited)
        return TeachingReply(response=text, generation_mode="native_tools",
                             response_variant="tool_loop", history_scope="durable_thread",
                             dialogue_state=self.ctx.dialogue_state,
                             source_refs=self.ctx.source_refs)

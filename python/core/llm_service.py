"""LLM service helpers for tutoring, hints, and quiz generation."""

from __future__ import annotations

import json
import logging
import os
import random
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LLMResponse(BaseModel):
    """Normalized model response."""

    content: str
    model: str
    usage: dict[str, int] = Field(default_factory=dict)


class TeachingReply(BaseModel):
    """Teacher-facing reply plus debug metadata."""

    response: str
    generation_mode: str
    response_variant: str
    history_scope: str
    dialogue_state: str = "answered"
    source_refs: list[str] = Field(default_factory=list)


class NativeToolCall(BaseModel):
    id: str
    name: str
    arguments: str


class NativeTurn(BaseModel):
    content: str = ""
    # 只用于当前工具循环回传；公开序列化和 repr 均不包含内部思考。
    reasoning_content: str | None = Field(default=None, exclude=True, repr=False)
    tool_calls: list[NativeToolCall] = Field(default_factory=list)
    stop_reason: str
    usage: dict[str, int] = Field(default_factory=dict)


QUESTION_BANK: dict[str, list[dict[str, Any]]] = {
    "vocab_basic": [
        {
            "question": 'Choose the correct meaning of "abundant" in the sentence: '
            '"The region has abundant natural resources."',
            "options": ["A. rare", "B. plentiful", "C. dangerous", "D. hidden"],
            "correct_index": 1,
            "explanation": 'abundant 表示“丰富的、充足的”，所以 "plentiful" 最贴切。',
        },
        {
            "question": 'What is the opposite of "abundant"?',
            "options": ["A. plentiful", "B. enough", "C. scarce", "D. useful"],
            "correct_index": 2,
            "explanation": 'scarce 表示“稀缺的”，和 abundant 构成反义关系。',
        },
        {
            "question": 'Choose the best word: "The teacher asked the students to ______ their essays by Friday."',
            "options": ["A. submit", "B. submit to", "C. submit for", "D. submit with"],
            "correct_index": 0,
            "explanation": '固定搭配是 "submit something"，直接接宾语，不需要额外介词。',
        },
    ],
    "vocab_intermediate": [
        {
            "question": 'Choose the best word: "She showed remarkable ______ during the crisis."',
            "options": ["A. eloquence", "B. resilience", "C. fragrance", "D. frequency"],
            "correct_index": 1,
            "explanation": "resilience 表示“韧性、恢复力”，最符合危机语境。",
        },
        {
            "question": 'Which word is closest in meaning to "elaborate"?',
            "options": ["A. simple", "B. detailed", "C. brief", "D. casual"],
            "correct_index": 1,
            "explanation": 'elaborate 常表示“详细的、展开充分的”，和 detailed 最接近。',
        },
    ],
    "grammar_tenses": [
        {
            "question": '"By the time you arrive, I ______ already ______." Choose the correct tense.',
            "options": ["A. will / leave", "B. will have / left", "C. am / leaving", "D. have / left"],
            "correct_index": 1,
            "explanation": "by the time 引出将来某时点之前已完成的动作，通常用将来完成时。",
        },
        {
            "question": '"She ______ English since 2020." Choose the correct tense.',
            "options": ["A. studies", "B. studied", "C. has been studying", "D. will study"],
            "correct_index": 2,
            "explanation": "since 2020 强调从过去持续到现在，常用现在完成进行时。",
        },
        {
            "question": "Which sentence uses the tense correctly?",
            "options": [
                "A. I am knowing the answer.",
                "B. I have been knowing her for years.",
                "C. I have known her for years.",
                "D. I am knowing her since yesterday.",
            ],
            "correct_index": 2,
            "explanation": "know 属于状态动词，通常不用进行时，因此 C 正确。",
        },
    ],
    "grammar_passive": [
        {
            "question": '"The letter ______ yesterday." Choose the correct passive form.',
            "options": ["A. was sent", "B. was send", "C. has been send", "D. is sent"],
            "correct_index": 0,
            "explanation": "过去时被动语态是 was/were + 过去分词，send 的过去分词是 sent。",
        },
        {
            "question": '"English ______ in many countries around the world." Choose the correct passive form.',
            "options": ["A. speaks", "B. is spoken", "C. was spoken", "D. has spoken"],
            "correct_index": 1,
            "explanation": "这里描述客观事实，应使用一般现在时的被动语态 is spoken。",
        },
    ],
    "reading_skimming": [
        {
            "question": "What is the main purpose of skimming?",
            "options": [
                "A. To understand every detail",
                "B. To quickly get the main idea",
                "C. To find one exact number",
                "D. To translate every sentence",
            ],
            "correct_index": 1,
            "explanation": "skimming 的核心是快速抓住文章大意，而不是逐句细读。",
        },
    ],
    "writing_paragraph": [
        {
            "question": "A standard English paragraph usually includes which three parts?",
            "options": [
                "A. beginning, body, ending",
                "B. topic sentence, supporting sentences, concluding sentence",
                "C. question, analysis, answer",
                "D. example, data, quote",
            ],
            "correct_index": 1,
            "explanation": "标准段落常见结构是 topic sentence、supporting sentences 和 concluding sentence。",
        },
    ],
}


def _normalize_option(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "", value)
    return value


def _history_to_text(conversation_history: list[dict[str, Any]] | None, limit: int = 6) -> str:
    if not conversation_history:
        return ""

    lines: list[str] = []
    for item in conversation_history[-limit:]:
        role = "学生" if item.get("role") == "student" else "老师"
        knowledge_id = item.get("knowledge_id")
        prefix = f"[{knowledge_id}] " if knowledge_id else ""
        lines.append(f"{role}: {prefix}{item.get('content', '')}")
    return "\n".join(lines)


def _extract_compatible_text_block(block: Any) -> tuple[str, str] | tuple[None, None]:
    """Best-effort extraction for Anthropic-compatible gateways."""
    candidates = ("text", "thinking", "content", "output_text", "summary")
    for field in candidates:
        value = getattr(block, field, None)
        if isinstance(value, str) and value.strip():
            return value.strip(), field
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())
                    continue
                nested = getattr(item, "text", None)
                if isinstance(nested, str) and nested.strip():
                    parts.append(nested.strip())
            if parts:
                return "\n".join(parts), field

    if isinstance(block, dict):
        for field in candidates:
            value = block.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip(), field

    return None, None


def _deterministic_index(seed: str, size: int, offset: int = 0) -> int:
    if size <= 0:
        return 0
    total = sum(ord(char) for char in seed) + offset
    return total % size


def _pick_variant(options: list[str], seed: str, offset: int = 0) -> tuple[str, int]:
    index = _deterministic_index(seed, len(options), offset)
    return options[index], index


def _last_relevant_history(history: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not history:
        return None

    for item in reversed(history[:-1] if len(history) > 1 else history):
        if item.get("content"):
            return item
    return None


def _infer_question_focus(knowledge_id: str, question: str) -> tuple[str, str]:
    lowered = question.lower()
    if knowledge_id.startswith("grammar_tenses") or any(
        token in lowered for token in ["since", "by the time", "already", "tense"]
    ):
        return ("时态", "先看时间线索，再判断动作是正在发生、已经完成，还是强调持续。")
    if knowledge_id.startswith("grammar_passive") or "passive" in lowered:
        return ("语态", "先看主语是不是动作的承受者，再判断要不要用 be + 过去分词。")
    if knowledge_id.startswith("vocab") and any(
        token in lowered for token in ["closest in meaning", "meaning", "opposite", "best word"]
    ):
        return ("词义", "先用句子语境缩小范围，再比较几个选项在感情色彩和搭配上的差别。")
    if knowledge_id.startswith("reading"):
        return ("阅读策略", "先确认题目要找的是主旨、细节还是推断，再决定是略读还是回到原文定位。")
    if knowledge_id.startswith("writing"):
        return ("写作结构", "先确认句子在段落里的作用，再决定它应该承担主题、支撑还是总结功能。")
    return ("线索", "先抓题干里最硬的判断线索，再用这个线索去排除明显不符的选项。")


def _classify_mistake(knowledge_id: str, question: str, student_answer: str, correct_answer: str) -> dict[str, str]:
    lowered = question.lower()
    if knowledge_id.startswith("grammar_tenses") or any(
        token in lowered for token in ["since", "by the time", "already", "tense"]
    ):
        return {
            "label": "时态误判",
            "rule": "先根据时间线索判断动作发生的先后，再选对应时态。",
            "next_step": "把题干里的时间提示词圈出来，再逐个排除不匹配的时态。",
        }
    if knowledge_id.startswith("grammar_passive") or "passive" in lowered:
        return {
            "label": "被动语态误判",
            "rule": "先判断主语是执行动作还是承受动作，再确认 be 动词和过去分词是否完整。",
            "next_step": "把主语和动词单独拎出来，看它们之间是不是“被做”的关系。",
        }
    if knowledge_id.startswith("vocab") and "best word" in lowered:
        return {
            "label": "搭配误判",
            "rule": "这类题不是只看词义接近，还要看这个词能不能和题干搭配得自然。",
            "next_step": "把你选的词和正确项分别代回句子，比较哪一个更顺更符合语境。",
        }
    if knowledge_id.startswith("vocab") and any(token in lowered for token in ["meaning", "closest", "opposite"]):
        return {
            "label": "词义误判",
            "rule": "这题核心是先定语境，再判断词义的方向、轻重和感情色彩。",
            "next_step": "先说出句子需要表达的意思，再看哪个选项最贴合这个意思。",
        }
    if student_answer and correct_answer:
        return {
            "label": "选项对比不足",
            "rule": "你已经缩小到了相近选项，但最后一步对比还不够细。",
            "next_step": "把你选的项和正确项并排比较，找出真正决定对错的那一个词或结构。",
        }
    return {
        "label": "线索忽略",
        "rule": "这题最关键的是先抓题干线索，再用线索推到选项。",
        "next_step": "回到题干，把最直接的提示词先圈出来，再重新判断。",
    }


class LLMService:
    """Provider wrapper with safe local fallbacks."""

    def __init__(
        self,
        provider: str = "template",
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        config_source: str = "none",
        fallback_reason: str | None = None,
        thinking: str = "disabled",
        reasoning_effort: str = "high",
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.model = model or self._get_default_model()
        self.config_source = config_source
        self.fallback_reason = fallback_reason
        self.thinking = thinking
        self.reasoning_effort = reasoning_effort
        self._client: Any = None

    def _get_default_model(self) -> str:
        if self.provider == "openai":
            return "gpt-4o"
        if self.provider == "anthropic":
            return "claude-3-sonnet-20240229"
        if self.provider == "minimax":
            return "MiniMax-M2.7"
        if self.provider == "deepseek":
            return "deepseek-flash"
        return "template"

    def _has_remote_llm(self) -> bool:
        return self.provider in {"openai", "anthropic", "minimax", "deepseek"} and bool(
            self.api_key
        )

    def ensure_ready(self) -> None:
        if not self._has_remote_llm():
            return
        self._get_client()

    def runtime_info(self) -> dict[str, Any]:
        return {
            "llm_enabled": self._has_remote_llm(),
            "provider": self.provider,
            "model": self.model,
            "config_source": self.config_source,
        }

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        if self.provider in {"openai", "deepseek"}:
            from openai import AsyncOpenAI
            from config.settings import settings

            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url or (
                    "https://api.deepseek.com" if self.provider == "deepseek" else None
                ),
                timeout=settings.llm_timeout_seconds,
                # 每轮模型调用只发一次请求，重试交给 Harness 管理。
                **({"max_retries": 0} if self.provider == "deepseek" else {}),
            )
        elif self.provider == "anthropic":
            from anthropic import AsyncAnthropic
            from config.settings import settings

            self._client = AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=settings.llm_timeout_seconds,
            )
        elif self.provider == "minimax":
            from openai import AsyncOpenAI
            from config.settings import settings

            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url or "https://api.minimax.chat/v1",
                timeout=settings.llm_timeout_seconds,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

        return self._client

    def _compatible_request_options(self, temperature: float) -> dict[str, Any]:
        if self.provider != "deepseek":
            return {"temperature": temperature}
        options: dict[str, Any] = {"extra_body": {"thinking": {"type": self.thinking}}}
        if self.thinking == "enabled":
            # 思考模式下 temperature 不生效，只传官方支持的思考强度。
            options["reasoning_effort"] = self.reasoning_effort
        else:
            options["temperature"] = temperature
        return options

    async def tool_turn(self, messages: list[dict], tools: list[dict], max_tokens: int) -> NativeTurn:
        """原生工具协议；失败直接上抛，由运行边界处理，不能伪装成正常回复。"""
        from core.run_context import active_run
        if ctx := active_run.get():
            ctx.consume("model")
        if os.getenv("PYTEST_CURRENT_TEST") and self._client is None:
            raise RuntimeError("Live model calls disabled in tests")
        if not self._has_remote_llm():
            raise RuntimeError("Native tools require a configured model")
        client = self._get_client()
        if self.provider == "anthropic":
            converted = []
            for message in messages:
                if message["role"] == "system":
                    continue
                if message["role"] == "tool":
                    converted.append({"role": "user", "content": [{
                        "type": "tool_result", "tool_use_id": message["tool_call_id"],
                        "content": message["content"],
                    }]})
                elif message["role"] == "assistant":
                    blocks = []
                    if message.get("content"):
                        blocks.append({"type": "text", "text": message["content"]})
                    for call in message.get("tool_calls", []):
                        blocks.append({"type": "tool_use", "id": call["id"],
                                       "name": call["function"]["name"],
                                       "input": json.loads(call["function"]["arguments"])})
                    converted.append({"role": "assistant", "content": blocks})
                else:
                    converted.append(message)
            response = await client.messages.create(
                model=self.model, max_tokens=max_tokens, temperature=0.3,
                system="\n".join(m["content"] for m in messages if m["role"] == "system"),
                messages=converted,
                tools=[{"name": t["function"]["name"], "description": t["function"]["description"],
                        "input_schema": t["function"]["parameters"]} for t in tools],
            )
            return NativeTurn(
                content="\n".join(b.text for b in response.content if b.type == "text"),
                tool_calls=[NativeToolCall(id=b.id, name=b.name, arguments=json.dumps(b.input))
                            for b in response.content if b.type == "tool_use"],
                stop_reason=response.stop_reason,
                usage={"input_tokens": response.usage.input_tokens,
                       "output_tokens": response.usage.output_tokens},
            )
        response = await client.chat.completions.create(
            model=self.model, messages=messages, tools=tools, tool_choice="auto",
            max_tokens=max_tokens,
            **self._compatible_request_options(temperature=0.3),
        )
        choice = response.choices[0]
        usage = (
            {"input_tokens": response.usage.prompt_tokens,
             "output_tokens": response.usage.completion_tokens}
            if response.usage else {}
        )
        if response.usage and self.provider == "deepseek":
            for name in ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
                value = getattr(response.usage, name, None)
                if isinstance(value, int):
                    usage[name] = value
        return NativeTurn(
            content=choice.message.content or "",
            reasoning_content=getattr(choice.message, "reasoning_content", None)
            if self.provider == "deepseek" and self.thinking == "enabled" else None,
            tool_calls=[NativeToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments)
                        for c in choice.message.tool_calls or []],
            stop_reason=choice.finish_reason or "unknown",
            usage=usage,
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return LLMResponse(content="", model=self.model, usage={})

        if not self._has_remote_llm():
            return LLMResponse(content="", model=self.model, usage={})

        from core.run_context import active_run
        ctx = active_run.get()
        if ctx:
            ctx.consume("model")
        try:
            client = self._get_client()

            if self.provider == "anthropic":
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt or "You are a helpful English teacher.",
                    messages=[{"role": "user", "content": prompt}],
                )
                content = ""
                content_source = ""
                block_types = [getattr(block, "type", type(block).__name__) for block in response.content]
                for block in response.content:
                    if getattr(block, "type", "") != "text":
                        continue
                    extracted, field = _extract_compatible_text_block(block)
                    if extracted:
                        content = extracted
                        content_source = field or "text"
                        break

                if not content:
                    for block in response.content:
                        extracted, field = _extract_compatible_text_block(block)
                        if extracted:
                            content = extracted
                            content_source = (
                                f"{getattr(block, 'type', type(block).__name__)}.{field or 'unknown'}"
                            )
                            logger.warning(
                                "Anthropic-compatible gateway returned no text block; using %s instead. "
                                "Block types: %s",
                                content_source,
                                block_types,
                            )
                            break

                if not content:
                    logger.warning(
                        "Anthropic returned no visible text block. Block types: %s",
                        block_types,
                    )
                    return LLMResponse(content="", model=self.model, usage={})
                usage = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                }
            else:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    **self._compatible_request_options(temperature=temperature),
                )
                content = response.choices[0].message.content or ""
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }

            if ctx:
                ctx.record("model_usage", ctx.role, task_id=ctx.task_id, usage=usage,
                           provider=self.provider, model=self.model)
            return LLMResponse(content=content.strip(), model=self.model, usage=usage)
        except Exception as exc:
            logger.error("LLM generation failed: %s", type(exc).__name__)
            return LLMResponse(content="", model=self.model, usage={})

    def build_quiz_evaluation_feedback(
        self,
        knowledge_id: str,
        question: str,
        student_answer: str,
        correct_answer: str,
        explanation: str = "",
        is_correct: bool = False,
    ) -> str:
        if is_correct:
            focus, rule = _infer_question_focus(knowledge_id, question)
            if explanation:
                return f"回答正确。你抓住了这题的{focus}线索。{explanation}"
            return f"回答正确。你抓住了这题的{focus}线索。{rule}"

        mistake = _classify_mistake(knowledge_id, question, student_answer, correct_answer)
        feedback = (
            f"这次主要问题是{mistake['label']}。你选了“{student_answer}”，正确答案是“{correct_answer}”。"
            f"{mistake['rule']}"
        )
        if explanation:
            return f"{feedback} {explanation}".strip()
        return feedback

    def _fallback_wrong_answer_response(
        self,
        knowledge_id: str,
        question: str,
        student_answer: str,
        correct_answer: str,
        evaluation_feedback: str,
        topic_history: list[dict[str, Any]] | None,
        variant_offset: int = 0,
    ) -> TeachingReply:
        mistake = _classify_mistake(knowledge_id, question, student_answer, correct_answer)
        seed = f"{knowledge_id}:{question}:{student_answer}:{correct_answer}"
        intro, intro_index = _pick_variant(
            [
                "先别急着看对错，我们先把这一步判断拆开。",
                "这题先不用背答案，关键是把判断依据找准。",
                "你这次卡住的不是记忆量，而是最后一步判断没有落稳。",
                "这题值得停一下，因为它暴露的是判断路径的问题。",
            ],
            seed,
            variant_offset,
        )
        bridge, _ = _pick_variant(
            [
                f"这里更像是{mistake['label']}，不是简单的粗心。",
                f"真正拉开差距的是你有没有看准这类题里的{mistake['label']}信号。",
                f"这题错在 {mistake['label']}，所以要回到最核心的规则上。",
                f"这一步的问题集中在{mistake['label']}，说明还需要把规则再压实一点。",
            ],
            seed + "bridge",
            variant_offset,
        )
        close, close_index = _pick_variant(
            [
                f"你先试着说说，当时为什么会把注意力落在“{student_answer}”上？",
                "你愿意先按这个规则自己重做一次，再告诉我你卡在哪一步吗？",
                f"你先把“{student_answer}”和“{correct_answer}”并排比一下，再说说你现在看到的关键差异。",
                "你先用一句话说出题干真正考的是什么，我们再顺着这一句继续拆。",
            ],
            seed + "close",
            variant_offset,
        )
        reference = ""
        previous = _last_relevant_history(topic_history)
        if previous and previous.get("context_type") in {"question", "submission", "wrong_answer"}:
            reference = "顺着你刚才这一轮的思路看，先不要换方法，先把判断顺序修正。"

        response = (
            f"{intro}{reference}{bridge}"
            f"{evaluation_feedback or mistake['rule']}"
            f"正确答案是“{correct_answer}”，因为它更符合这题需要的判断线索。"
            f"{mistake['next_step']}{close}"
        )
        return TeachingReply(
            response=response,
            generation_mode="local_fallback",
            response_variant=f"wrong-{intro_index}-{close_index}",
            history_scope="topic_thread" if topic_history else "session_recent",
        )

    def _fallback_question_response(
        self,
        knowledge_id: str,
        question: str,
        topic_history: list[dict[str, Any]] | None,
        session_history: list[dict[str, Any]] | None,
        variant_offset: int = 0,
        recent_submission: dict[str, str] | None = None,
    ) -> TeachingReply:
        lowered = question.lower()
        context_text = " ".join(str(value) for value in (recent_submission or {}).values()).lower()
        if "submit" in lowered or "submit" in context_text:
            correct_answer = (recent_submission or {}).get("correct_answer", "submit")
            if "submit to" in lowered:
                response = (
                    '"submit to" 常见有两个意思：一是“屈服于、服从”，比如 submit to authority；'
                    '二是“把某物提交给某人/机构”，结构通常是 submit something to someone。'
                    f"这道题选“{correct_answer}”，因为空格后面直接是 their essays，表示提交的东西，"
                    "所以用 submit their essays，不需要加 to。"
                )
            elif "介词" in question or "搭配" in question:
                response = (
                    "介词搭配就是看动词后面要不要接介词、接哪个介词，以及介词后面接什么对象。"
                    "submit 可以直接接提交的东西：submit an essay；如果要说明提交给谁，才说 submit an essay to the teacher。"
                    "本题空格后已经直接接 their essays，所以介词 to 是多余的。"
                )
            elif "为什么" in question or "为啥" in question or "空格后面" in question or "选submit" in lowered:
                response = (
                    f"这题选“{correct_answer}”是因为空格后面直接跟着 their essays。"
                    "essays 是“被提交的东西”，submit 本身是及物动词，可以直接说 submit their essays。"
                    "submit to 后面通常接“人、机构、权威”或表示“屈服于某事物”，不适合直接接这里的 essays。"
                )
            else:
                response = (
                    "这里要分清 submit 和 submit to：submit something 表示提交某物；"
                    "submit something to someone 表示把某物提交给某人/机构；submit to something 还可以表示屈服于。"
                    "本题后面已经是 their essays，所以直接用 submit。"
                )
            return TeachingReply(
                response=response,
                generation_mode="local_fallback",
                response_variant="question-submit-direct",
                history_scope="topic_thread" if topic_history or recent_submission else "session_recent",
            )

        focus, rule = _infer_question_focus(knowledge_id, question)
        seed = f"{knowledge_id}:{question}"
        intro, intro_index = _pick_variant(
            [
                f"这次你问的核心其实是{focus}判断。",
                f"先直接回答你这句：这题先看{focus}，不要先看选项表面差别。",
                f"你这个问题可以直接落到{focus}上，不用先绕大圈。",
                f"这类问题先抓{focus}，答案就会稳定很多。",
            ],
            seed,
            variant_offset,
        )
        close, close_index = _pick_variant(
            [
                "如果你愿意，把最卡的那一句贴出来，我就按这个顺序继续带你拆。",
                "你先按这个思路自己判断一遍，再把你犹豫的那一步发给我。",
                "如果你想，我们下一轮就只盯最难的那个选项来比。",
                "你先试着用一句话复述题干在考什么，我再帮你校正。",
            ],
            seed + "close",
            variant_offset,
        )

        reference = ""
        previous = _last_relevant_history(topic_history)
        history_scope = "topic_thread"
        if previous:
            if previous.get("context_type") == "submission":
                reference = "延续你上一题的思路，这次仍然先看题干线索，再决定选项。"
            elif previous.get("context_type") == "question":
                reference = "和你上一轮追问一样，这里也不要先背结论，先抓判断依据。"
        elif session_history:
            history_scope = "session_recent"
            reference = "虽然这次不是同一道题，但还是先沿用你前面练过的“先看线索、再排选项”的顺序。"

        response = f"{intro}{rule}{reference}{close}"
        return TeachingReply(
            response=response,
            generation_mode="local_fallback",
            response_variant=f"question-{intro_index}-{close_index}",
            history_scope=history_scope,
        )

    def _fallback_hint_response(
        self,
        knowledge_id: str,
        hint_level: int,
        hint_count: int,
        topic_history: list[dict[str, Any]] | None,
        variant_offset: int = 0,
    ) -> TeachingReply:
        focus, rule = _infer_question_focus(knowledge_id, "")
        seed = f"{knowledge_id}:{hint_level}:{hint_count}"
        if hint_level == 1:
            text, index = _pick_variant(
                [
                    f"先别翻答案，先只看题干。和这道题最相关的第一条{focus}线索是什么？",
                    f"先把注意力收回来，只找一个最硬的{focus}提示词，再决定怎么选。",
                    f"这一步先别比四个选项，先确认题干有没有给出明确的{focus}信号。",
                ],
                seed,
                variant_offset,
            )
        elif hint_level == 2:
            text, index = _pick_variant(
                [
                    f"给你一个排除顺序：先用{focus}线索排掉最不可能的两个，再在剩下两个里细比。",
                    f"现在不要整体看四个选项，先问自己哪两个和题干的{focus}要求明显不符。",
                    f"你可以先按“题干线索 -> 排除两个 -> 细比两个”的顺序走一遍。",
                ],
                seed,
                variant_offset,
            )
        else:
            text, index = _pick_variant(
                [
                    f"更具体一点，这题真正决定对错的就是这一条规则：{rule}",
                    f"我把突破口缩小到一句：先按这个规则判断，{rule}",
                    f"最后这一步不要再靠感觉，直接回到规则：{rule}",
                ],
                seed,
                variant_offset,
            )

        previous = _last_relevant_history(topic_history)
        if previous and previous.get("context_type") == "hint":
            text = f"{text} 这次尽量换个角度看，不要重复上一轮的排法。"

        return TeachingReply(
            response=text,
            generation_mode="local_fallback",
            response_variant=f"hint-{hint_level}-{index}",
            history_scope="topic_thread" if topic_history else "session_recent",
        )

    async def generate_answer_wrong_response(
        self,
        knowledge_id: str,
        level: str,
        mastery: float,
        question: str,
        student_answer: str,
        correct_answer: str,
        evaluation_feedback: str,
        topic_history: list[dict[str, Any]] | None = None,
        session_history: list[dict[str, Any]] | None = None,
        avoid_responses: list[str] | None = None,
        variant_offset: int = 0,
        learner_context: str = "",
    ) -> TeachingReply:
        fallback = self._fallback_wrong_answer_response(
            knowledge_id=knowledge_id,
            question=question,
            student_answer=student_answer,
            correct_answer=correct_answer,
            evaluation_feedback=evaluation_feedback,
            topic_history=topic_history,
            variant_offset=variant_offset,
        )
        topic_history_text = _history_to_text(topic_history)
        session_history_text = _history_to_text(session_history)
        avoid_text = ""
        if avoid_responses:
            avoid_text = "\n避免重复这些表达：\n" + "\n".join(avoid_responses[-2:])

        prompt = (
            f"学生在知识点 {knowledge_id} 上答错了。\n"
            f"当前掌握水平: {level}, mastery={mastery:.0%}\n"
            f"题目: {question}\n"
            f"学生答案: {student_answer}\n"
            f"正确答案: {correct_answer}\n"
            f"客观判定: {evaluation_feedback}\n"
            "请用 3-4 句中文老师回复："
            "先直接指出本次错因，再解释关键规则，再给一个简短追问。"
            "不要用固定开场，不要输出 markdown，不要泄露思维链。"
            f"{avoid_text}"
        )
        if learner_context:
            prompt = f"学生画像：{learner_context}\n\n{prompt}"
        if topic_history_text:
            prompt = f"当前知识点最近对话：\n{topic_history_text}\n\n{prompt}"
        elif session_history_text:
            prompt = f"当前页面最近对话：\n{session_history_text}\n\n{prompt}"

        response = await self.generate(
            prompt=prompt,
            system_prompt="你是一位耐心、直接、具体的英语老师，先回答当前问题，再顺带承接上下文。",
            temperature=0.45,
            max_tokens=320,
        )
        if response.content:
            return TeachingReply(
                response=response.content,
                generation_mode="remote_llm",
                response_variant=f"{self.provider}:{self.model}",
                history_scope="topic_thread" if topic_history else "session_recent",
            )
        return fallback

    async def generate_student_question_response(
        self,
        knowledge_id: str,
        question: str,
        topic_history: list[dict[str, Any]] | None = None,
        session_history: list[dict[str, Any]] | None = None,
        avoid_responses: list[str] | None = None,
        variant_offset: int = 0,
        learner_context: str = "",
        recent_submission: dict[str, str] | None = None,
    ) -> TeachingReply:
        fallback = self._fallback_question_response(
            knowledge_id=knowledge_id,
            question=question,
            topic_history=topic_history,
            session_history=session_history,
            variant_offset=variant_offset,
            recent_submission=recent_submission,
        )
        topic_history_text = _history_to_text(topic_history)
        session_history_text = _history_to_text(session_history)
        recent_submission_text = ""
        if recent_submission:
            recent_submission_text = (
                "最近一道题上下文：\n"
                f"题目：{recent_submission.get('question', '')}\n"
                f"学生答案：{recent_submission.get('student_answer', '')}\n"
                f"正确答案：{recent_submission.get('correct_answer', '')}\n"
                f"判定反馈：{recent_submission.get('evaluation_feedback', '')}\n"
                f"解释：{recent_submission.get('explanation', '')}\n"
            )
        avoid_text = ""
        if avoid_responses:
            avoid_text = "\n不要重复这些表达：\n" + "\n".join(avoid_responses[-2:])

        prompt = (
            f"学生围绕知识点 {knowledge_id} 提问：{question}\n"
            "请用 3-4 句中文老师回复："
            "第一句必须先直接回答这次问题，不要只说“抓线索”。"
            "如果学生问为什么、什么意思、分不清、介词搭配，必须解释具体概念和例子。"
            "第二句补关键判断依据，最后给一个很短的下一步建议或追问。"
            "如果有上下文，只简短承接，不要用长模板回顾历史。"
            "不要输出 markdown，不要泄露思维链。"
            f"{avoid_text}"
        )
        if learner_context:
            prompt = f"学生画像：{learner_context}\n\n{prompt}"
        if recent_submission_text:
            prompt = f"{recent_submission_text}\n{prompt}"
        if topic_history_text:
            prompt = f"当前知识点最近对话：\n{topic_history_text}\n\n{prompt}"
        elif session_history_text:
            prompt = f"当前页面最近对话：\n{session_history_text}\n\n{prompt}"

        response = await self.generate(
            prompt=prompt,
            system_prompt="你是一位耐心、直接、具体的英语老师，优先回答当前问题，不要套固定寒暄模板。",
            temperature=0.5,
            max_tokens=420,
        )
        if response.content:
            return TeachingReply(
                response=response.content,
                generation_mode="remote_llm",
                response_variant=f"{self.provider}:{self.model}",
                history_scope="topic_thread" if topic_history else "session_recent",
            )
        return fallback

    async def generate_hint_response(
        self,
        knowledge_id: str,
        hint_level: int,
        hint_count: int,
        topic_history: list[dict[str, Any]] | None = None,
        session_history: list[dict[str, Any]] | None = None,
        avoid_responses: list[str] | None = None,
        variant_offset: int = 0,
        learner_context: str = "",
    ) -> TeachingReply:
        fallback = self._fallback_hint_response(
            knowledge_id=knowledge_id,
            hint_level=hint_level,
            hint_count=hint_count,
            topic_history=topic_history,
            variant_offset=variant_offset,
        )
        topic_history_text = _history_to_text(topic_history)
        session_history_text = _history_to_text(session_history)
        avoid_text = ""
        if avoid_responses:
            avoid_text = "\n避免重复这些提示：\n" + "\n".join(avoid_responses[-2:])

        prompt = (
            f"学生在知识点 {knowledge_id} 上已经请求了 {hint_count} 次提示，当前提示级别是 {hint_level}。\n"
            "请生成 2-3 句中文提示，要求只给方向和关键规则，不直接说答案。"
            "同级别提示不要重复上一轮表达。"
            "不要输出 markdown，不要泄露思维链。"
            f"{avoid_text}"
        )
        if learner_context:
            prompt = f"学生画像：{learner_context}\n\n{prompt}"
        if topic_history_text:
            prompt = f"当前知识点最近对话：\n{topic_history_text}\n\n{prompt}"
        elif session_history_text:
            prompt = f"当前页面最近对话：\n{session_history_text}\n\n{prompt}"

        response = await self.generate(
            prompt=prompt,
            system_prompt="你是一位有分层提示意识的英语老师，提示要短、准、不要重复。",
            temperature=0.4,
            max_tokens=220,
        )
        if response.content:
            return TeachingReply(
                response=response.content,
                generation_mode="remote_llm",
                response_variant=f"{self.provider}:{self.model}",
                history_scope="topic_thread" if topic_history else "session_recent",
            )
        return fallback

    async def generate_message_response(
        self,
        knowledge_id: str,
        message: str,
        topic_history: list[dict[str, Any]] | None = None,
        session_history: list[dict[str, Any]] | None = None,
        avoid_responses: list[str] | None = None,
        variant_offset: int = 0,
        learner_context: str = "",
    ) -> TeachingReply:
        return await self.generate_student_question_response(
            knowledge_id=knowledge_id,
            question=message,
            topic_history=topic_history,
            session_history=session_history,
            avoid_responses=avoid_responses,
            variant_offset=variant_offset,
            learner_context=learner_context,
        )

    async def generate_engagement_assessment(
        self,
        engagement_data: dict[str, Any],
    ) -> LLMResponse:
        prompt = (
            f"学生学习行为数据：\n"
            f"- 会话时长：{engagement_data.get('session_minutes', 0):.0f}分钟\n"
            f"- 最近10题正确率：{engagement_data.get('recent_accuracy', 0.5):.0%}\n"
            f"- 连续答错：{engagement_data.get('consecutive_errors', 0)}次\n"
            f"- 连续答对：{engagement_data.get('consecutive_correct', 0)}次\n"
            f"- 最近答题速度趋势：{engagement_data.get('speed_trend', '正常')}\n"
            f"- 最近练习的知识点：{engagement_data.get('recent_topics', '无')}\n"
            f"\n请判断学生当前学习状态，只返回JSON，不要其他内容："
            f'{{"state": "focused/struggling/frustrated/bored/fatigued/idle", '
            f'"reason": "简短原因", '
            f'"suggestion": "给教学系统的建议（中文）"}}'
        )
        return await self.generate(
            prompt=prompt,
            system_prompt="你是学习行为分析专家，根据行为数据判断学生状态。只返回JSON。",
            temperature=0.3,
            max_tokens=200,
        )

    async def generate_next_topic_recommendation(
        self,
        candidate_topics: list[dict[str, Any]],
        learner_profile: dict[str, Any],
    ) -> LLMResponse:
        candidates_text = "\n".join(
            f"- {t['name']}（难度{t['difficulty']:.1f}，ID: {t['id']}）"
            for t in candidate_topics
        )
        prompt = (
            f"学生学习画像：\n"
            f"- 已掌握的知识点：{learner_profile.get('mastered', '无')}\n"
            f"- 薄弱项：{learner_profile.get('weak_points', '无')}\n"
            f"- 平均掌握度：{learner_profile.get('avg_mastery', 0):.0%}\n"
            f"- 本次会话已练习：{learner_profile.get('session_topics', '无')}\n"
            f"\n可选的下一个知识点（前置知识已满足）：\n{candidates_text}"
            f"\n\n请推荐最适合的下一个知识点，只返回JSON，不要其他内容："
            f'{{"knowledge_id": "推荐的知识点ID", "reason": "推荐理由（中文，2-3句话）"}}'
        )
        return await self.generate(
            prompt=prompt,
            system_prompt="你是英语课程规划专家，根据学生画像推荐学习路径。只返回JSON。",
            temperature=0.4,
            max_tokens=200,
        )

    async def generate_weakness_diagnosis(
        self,
        knowledge_id: str,
        question: str,
        student_answer: str,
        correct_answer: str,
        mastery: float,
        attempts: int,
        weak_points: list[str],
    ) -> LLMResponse:
        prompt = (
            f"学生在知识点 {knowledge_id} 上连续答错 {attempts} 次，掌握度仅 {mastery:.0%}。\n"
            f"题目：{question}\n学生答案：{student_answer}\n正确答案：{correct_answer}\n"
            f"该生其他薄弱项：{', '.join(weak_points) if weak_points else '无'}\n"
            f"\n请诊断这个学生的根本问题，只返回JSON，不要其他内容："
            f'{{"diagnosis": "诊断分析（中文）", "suggestion": "给学生的具体建议（中文）"}}'
        )
        return await self.generate(
            prompt=prompt,
            system_prompt="你是英语学习诊断专家，分析学生错误模式并给出个性化建议。只返回JSON。",
            temperature=0.3,
            max_tokens=200,
        )

    async def generate_assessment_strategy(
        self,
        assessment_data: dict[str, Any],
    ) -> LLMResponse:
        prompt = (
            "请根据学生本次答题评估，给 Assessment Agent 一个策略判断。只返回 JSON，不要其他内容。\n"
            f"知识点：{assessment_data.get('knowledge_id', '')}\n"
            f"是否答对：{assessment_data.get('is_correct', False)}\n"
            f"掌握度：{assessment_data.get('mastery', 0):.0%}\n"
            f"尝试次数：{assessment_data.get('attempts', 0)}\n"
            f"连续正确：{assessment_data.get('streak', 0)}\n"
            f"错误模式：{assessment_data.get('error_patterns', [])}\n"
            f"题目：{assessment_data.get('question', '')}\n"
            f"学生答案：{assessment_data.get('student_answer', '')}\n"
            f"正确答案：{assessment_data.get('correct_answer', '')}\n"
            '\nJSON 格式：{"diagnosis": "错因/掌握状态诊断", '
            '"confidence": 0.0, "recommended_action": "remediate/practice/advance/review", '
            '"student_message": "给学生看的简短建议"}'
        )
        return await self.generate(
            prompt=prompt,
            system_prompt="你是英语学习评估智能体，负责诊断掌握状态并给出下一步策略。只返回 JSON。",
            temperature=0.25,
            max_tokens=260,
        )

    async def generate_curriculum_strategy(
        self,
        curriculum_data: dict[str, Any],
    ) -> LLMResponse:
        candidates = curriculum_data.get("candidates", [])
        candidates_text = "\n".join(
            f"- {item.get('id', '')}: {item.get('name', '')}, 难度 {item.get('difficulty', 0):.1f}"
            for item in candidates
        ) or "无"
        prompt = (
            "请根据学习路径和复习状态，给 Curriculum Agent 一个课程策略。只返回 JSON，不要其他内容。\n"
            f"当前知识点：{curriculum_data.get('knowledge_id', '')}\n"
            f"掌握度：{curriculum_data.get('mastery', 0):.0%}\n"
            f"薄弱项：{curriculum_data.get('weak_points', '无')}\n"
            f"已掌握：{curriculum_data.get('mastered', '无')}\n"
            f"可选下一知识点：\n{candidates_text}\n"
            f"到期复习项：{curriculum_data.get('due_items', [])}\n"
            '\nJSON 格式：{"plan": "课程安排策略", '
            '"next_action": "review/remediate/practice/advance", '
            '"target_knowledge_id": "知识点ID", "reason": "简短理由"}'
        )
        return await self.generate(
            prompt=prompt,
            system_prompt="你是英语课程规划智能体，负责平衡推进、复习和补救。只返回 JSON。",
            temperature=0.35,
            max_tokens=260,
        )

    async def generate_teaching_decision(
        self,
        decision_context: dict[str, Any],
    ) -> LLMResponse:
        prompt = (
            "请综合多个 Agent 的输出，生成本轮最终教学决策。只返回 JSON，不要其他内容。\n"
            f"学习者：{decision_context.get('learner_id', '')}\n"
            f"当前知识点：{decision_context.get('knowledge_id', '')}\n"
            f"交互类型：{decision_context.get('interaction_type', '')}\n"
            f"Assessment：{decision_context.get('assessment', {})}\n"
            f"Tutor：{decision_context.get('tutor', {})}\n"
            f"Curriculum：{decision_context.get('curriculum', {})}\n"
            f"Engagement：{decision_context.get('engagement', {})}\n"
            '\nJSON 格式：{"strategy": "answer_question/remediate/practice/review/advance/encourage", '
            '"priority": "low/normal/high", "summary": "一句话总结", '
            '"next_action": "下一步动作", "rationale": "为什么这样决策"}'
        )
        return await self.generate(
            prompt=prompt,
            system_prompt="你是教学决策协调器，负责整合评估、辅导、课程和参与度 Agent。只返回 JSON。",
            temperature=0.3,
            max_tokens=320,
        )

    async def generate_question(
        self,
        knowledge_id: str,
        difficulty: float = 0.5,
    ) -> dict[str, Any]:
        bank = QUESTION_BANK.get(knowledge_id, [])
        if bank:
            quiz = dict(random.choice(bank))
            quiz["source"] = "bank"
            quiz["difficulty"] = difficulty
            return quiz

        if self._has_remote_llm():
            diff_desc = "easy" if difficulty < 0.3 else "medium" if difficulty < 0.7 else "hard"
            prompt = (
                f"Generate one {diff_desc} English multiple-choice question about {knowledge_id}. "
                'Return only JSON with keys question, options, correct_index, explanation. '
                "Exactly four options."
            )
            response = await self.generate(
                prompt=prompt,
                system_prompt=(
                    "You are an English quiz writer for Chinese learners. "
                    "Keep the question clear and the explanation concise in Chinese."
                ),
                temperature=0.7,
                max_tokens=400,
            )
            try:
                match = re.search(r"\{.*\}", response.content, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    options = parsed.get("options", [])
                    if (
                        isinstance(parsed.get("question"), str)
                        and isinstance(options, list)
                        and len(options) == 4
                        and isinstance(parsed.get("correct_index"), int)
                    ):
                        parsed["source"] = "llm"
                        parsed["difficulty"] = difficulty
                        return parsed
            except Exception as exc:
                logger.warning("Failed to parse LLM quiz output: %s", exc)

        return self._get_fallback_question(knowledge_id, difficulty)

    def _get_fallback_question(self, knowledge_id: str, difficulty: float) -> dict[str, Any]:
        return {
            "question": f"About {knowledge_id}, which statement is the most appropriate?",
            "options": [
                "A. This is a basic knowledge point.",
                "B. This is always an advanced structure.",
                "C. This knowledge point is never useful.",
                "D. None of the above.",
            ],
            "correct_index": 0,
            "explanation": f"这是一道关于 {knowledge_id} 的兜底题，重点是先确认核心规则。",
            "source": "fallback",
            "difficulty": difficulty,
        }

    async def evaluate_answer(
        self,
        knowledge_id: str,
        question: str,
        student_answer: str,
        correct_answer: str = "",
    ) -> dict[str, Any]:
        if correct_answer:
            is_correct = _normalize_option(student_answer) == _normalize_option(correct_answer)
            return {
                "is_correct": is_correct,
                "score": 1.0 if is_correct else 0.0,
                "feedback": self.build_quiz_evaluation_feedback(
                    knowledge_id=knowledge_id,
                    question=question,
                    student_answer=student_answer,
                    correct_answer=correct_answer,
                    is_correct=is_correct,
                ),
            }

        if self._has_remote_llm():
            prompt = (
                f"知识点: {knowledge_id}\n题目: {question}\n学生回答: {student_answer}\n"
                '请返回 JSON: {"is_correct": bool, "score": float, "feedback": "中文简短反馈"}'
            )
            response = await self.generate(
                prompt=prompt,
                system_prompt="你是一位英语主观题评分老师，只输出 JSON。",
                temperature=0.2,
                max_tokens=240,
            )
            try:
                match = re.search(r"\{.*\}", response.content, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    if "is_correct" in parsed:
                        return parsed
            except Exception as exc:
                logger.warning("Failed to parse answer evaluation: %s", exc)

        return {
            "is_correct": False,
            "score": 0.0,
            "feedback": "暂时无法可靠评判这道主观题，请换成选择题或补充标准答案。",
        }


_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Return a singleton service based on available configuration."""

    global _llm_service
    if _llm_service is None:
        from config.settings import settings

        provider = settings.configured_llm_provider
        config_source = settings.llm_config_source

        if provider == "anthropic":
            candidate = LLMService(
                provider="anthropic",
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url,
                model=settings.model_id,
                config_source=config_source,
            )
        elif provider == "openai":
            candidate = LLMService(
                provider="openai",
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.openai_model,
                config_source=config_source,
            )
        elif provider == "minimax":
            candidate = LLMService(
                provider="minimax",
                api_key=settings.minimax_api_key,
                model=settings.minimax_model,
                config_source=config_source,
            )
        elif provider == "deepseek":
            candidate = LLMService(
                provider="deepseek",
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
                config_source=config_source,
                thinking=settings.deepseek_thinking,
                reasoning_effort=settings.deepseek_reasoning_effort,
            )
        else:
            logger.warning("No remote LLM configured, using local template responses")
            _llm_service = LLMService(
                provider="template",
                model="template",
                config_source=config_source,
                fallback_reason="no_config",
            )
            return _llm_service

        try:
            candidate.ensure_ready()
            logger.info(
                "Remote LLM enabled: provider=%s model=%s source=%s",
                candidate.provider,
                candidate.model,
                config_source,
            )
            _llm_service = candidate
        except Exception as exc:
            logger.error("Remote LLM initialization failed, falling back to template mode: %s",
                         type(exc).__name__)
            _llm_service = LLMService(
                provider="template",
                model="template",
                config_source=config_source,
                fallback_reason="client_init_failed",
            )

    return _llm_service

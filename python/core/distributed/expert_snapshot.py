"""构建显式脱敏专家快照，并仅在快照上执行有界只读工具。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from typing import Any

from pydantic import ValidationError

from config.settings import settings
from core.coordination_budget import practice_policy
from core.llm_service import NativeToolCall
from core.output_safety import has_secret_shaped_key, public_value
from core.tool_executor import REGISTRY, ToolResult, ToolSpec, ToolExecutor

from .expert_contracts import ExpertRole, ExpertSnapshot, HistoryRecord


READ_TOOL_NAMES = frozenset({
    "search_learning_history",
    "read_learning_history",
    "get_knowledge_context",
    "get_learner_profile",
    "get_review_queue",
})
CALL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _json_bytes(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    )


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return EPOCH


class ExpertSnapshotBuilder:
    """父运行侧构建器；只复制协议明确列出的字段。"""

    def __init__(
        self,
        *,
        max_snapshot_bytes: int | None = None,
        max_history_bytes: int | None = None,
        max_history_records: int = 20,
    ):
        self.max_snapshot_bytes = (
            max_snapshot_bytes
            if max_snapshot_bytes is not None
            else settings.expert_max_payload_bytes
        )
        self.max_history_bytes = (
            max_history_bytes
            if max_history_bytes is not None
            else self.max_snapshot_bytes // 2
        )
        if self.max_snapshot_bytes < 1 or self.max_history_bytes < 0:
            raise ValueError("snapshot byte limits must be non-negative")
        if max_history_records < 0:
            raise ValueError("max_history_records must be non-negative")
        self.max_history_records = max_history_records

    def freeze(self, ctx, step, plan, authority) -> ExpertSnapshot:
        del authority  # 权限对象属于作业信封，不复制到学习事实快照。
        role = ExpertRole(getattr(step, "agent", getattr(step, "role", step)))
        stable_memories = public_value(ctx.history.memory.profile(ctx.learner))
        knowledge_context = public_value(
            ToolExecutor(ctx).knowledge_context(ctx.knowledge_id)
        )
        records = self._history_records(ctx)
        verified = set(getattr(ctx, "source_refs", ()))
        verified.update(
            item["source_ref"]
            for item in stable_memories
            if isinstance(item, dict) and isinstance(item.get("source_ref"), str)
        )
        verified.update(
            item.get("source_ref")
            for item in getattr(ctx, "read_evidence", {}).values()
            if isinstance(item, dict) and isinstance(item.get("source_ref"), str)
        )
        included_refs = {record.source_ref for record in records}
        stable_refs = {
            item["source_ref"]
            for item in stable_memories
            if isinstance(item, dict) and isinstance(item.get("source_ref"), str)
        }

        values = public_value({
            "learner_id": ctx.learner,
            "knowledge_id": ctx.knowledge_id,
            "current_input": ctx.input_text,
            "student_inputs": list(plan.student_inputs),
            "goal": plan.goal,
            "constraints": list(plan.constraints),
            "effective_policy_hash": ctx.effective_policy_hash,
            "practice_policy": practice_policy(ctx, plan),
            "knowledge_state": ctx.model_state,
            "learner_profile": ctx.profile_state,
            "review_queue": ctx.review_queue,
            "knowledge_context": knowledge_context,
            "quiz_context": self._quiz_context(getattr(ctx, "quiz", None)),
            "stable_memories": stable_memories,
            "history_records": [
                record.model_dump(mode="python") for record in records
            ],
            "verified_source_refs": sorted(
                ref for ref in verified if ref in included_refs | stable_refs
            )[:64],
        })
        snapshot = ExpertSnapshot.model_validate(values)

        while (
            _json_bytes(snapshot.model_dump(mode="json")) > self.max_snapshot_bytes
            and snapshot.history_records
        ):
            values["history_records"].pop()
            included_refs = {
                record["source_ref"] for record in values["history_records"]
            }
            values["verified_source_refs"] = [
                ref
                for ref in values["verified_source_refs"]
                if ref in included_refs | stable_refs
            ]
            snapshot = ExpertSnapshot.model_validate(values)
        if _json_bytes(snapshot.model_dump(mode="json")) > self.max_snapshot_bytes:
            raise ValueError("expert snapshot exceeds byte limit")
        if has_secret_shaped_key(snapshot.model_dump(mode="python")):
            raise ValueError("expert snapshot contains a secret-shaped key")
        # Role conversion above rejects unsupported expert roles before work is queued.
        _ = role
        return snapshot

    @staticmethod
    def _quiz_context(quiz: Any) -> dict[str, Any] | None:
        if not quiz:
            return None
        return {
            key: deepcopy(quiz[key])
            for key in ("question", "options", "knowledge_id")
            if key in quiz
        }

    def _history_records(self, ctx) -> list[HistoryRecord]:
        metadata: dict[str, dict[str, Any]] = {}
        discovery = ctx.history.discovery(
            ctx.learner, ctx.knowledge_id, limit=self.max_history_records
        )
        for item in discovery.get("items", []):
            if isinstance(item, dict) and isinstance(item.get("source_ref"), str):
                metadata[item["source_ref"]] = item
        for item in getattr(ctx, "read_evidence", {}).values():
            if isinstance(item, dict) and isinstance(item.get("source_ref"), str):
                metadata[item["source_ref"]] = item
        for source_ref in getattr(ctx, "source_refs", ()):
            if isinstance(source_ref, str):
                metadata.setdefault(source_ref, {"source_ref": source_ref})

        records: list[HistoryRecord] = []
        used = 0
        for source_ref in sorted(metadata):
            if len(records) >= self.max_history_records:
                break
            record = self._full_record(ctx, source_ref, metadata[source_ref])
            if record is None:
                continue
            size = _json_bytes(record.model_dump(mode="json"))
            if used + size > self.max_history_bytes:
                continue
            records.append(record)
            used += size
        return records

    @staticmethod
    def _full_record(ctx, source_ref: str, metadata: dict[str, Any]) -> HistoryRecord | None:
        try:
            data = ctx.history.read(ctx.learner, source_ref, 0, 16000)
        except Exception:
            return None
        if not isinstance(data, dict) or data.get("truncated"):
            return None
        if "content" in data:
            content = data["content"]
        elif "data" in data:
            content = json.dumps(data["data"], ensure_ascii=False, sort_keys=True)
        else:
            return None
        if not isinstance(content, str) or len(content) > 16000:
            return None
        clean = public_value({**metadata, **data, "content": content})
        knowledge_id = clean.get("knowledge_id")
        if not isinstance(knowledge_id, str) or not knowledge_id:
            knowledge_id = ctx.knowledge_id
        role = str(clean.get("role") or clean.get("kind") or "history")[:32]
        return HistoryRecord(
            source_ref=source_ref,
            role=role,
            recorded_at=_timestamp(
                clean.get("recorded_at")
                or clean.get("created")
                or clean.get("updated_at")
            ),
            knowledge_id=knowledge_id,
            content=clean["content"],
        )


class SnapshotToolExecutor:
    """无存储依赖的快照读取器，并在本实例内跟踪完整读取范围。"""

    def __init__(self, snapshot: ExpertSnapshot, role: ExpertRole | str):
        self.snapshot = snapshot
        self.role = ExpertRole(role).value
        self.registry: dict[str, ToolSpec] = {
            name: REGISTRY[name] for name in READ_TOOL_NAMES
        }
        self._seen_call_ids: set[str] = set()
        self._verified_source_refs = set(snapshot.verified_source_refs)
        self._read_ranges: dict[str, list[tuple[int, int]]] = {}
        self._read_counter = 0
        self._records = {
            record.source_ref: record for record in snapshot.history_records
        }

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(
            name
            for name, spec in self.registry.items()
            if self.role in spec.roles
        ))

    @property
    def verified_source_refs(self) -> tuple[str, ...]:
        return tuple(sorted(self._verified_source_refs))

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": self.registry[name].description,
                    "parameters": self.registry[name].schema.model_json_schema(),
                },
            }
            for name in self.tool_names
        ]

    async def read(
        self, source_ref: str, offset: int = 0, limit: int = 3000
    ) -> dict[str, Any]:
        self._read_counter += 1
        return await self.execute(NativeToolCall(
            id=f"snapshot-read-{self._read_counter}",
            name="read_learning_history",
            arguments=json.dumps({
                "source_ref": source_ref,
                "offset": offset,
                "limit": limit,
            }),
        ))

    async def execute(self, call: NativeToolCall) -> dict[str, Any]:
        result = self._result()
        if not CALL_ID.fullmatch(call.id):
            result.update(status="invalid_arguments", error_code="invalid_call_id")
            return self._validated(result)
        if call.id in self._seen_call_ids:
            result.update(status="invalid_arguments", error_code="duplicate_call_id")
            return self._validated(result)
        self._seen_call_ids.add(call.id)

        spec = self.registry.get(call.name)
        if spec is None or call.name not in self.tool_names:
            result["error_code"] = "unavailable_or_not_allowed"
            return self._validated(result)
        try:
            params = spec.schema.model_validate_json(call.arguments)
        except ValidationError as exc:
            result.update(
                status="invalid_arguments",
                error_code="schema_validation",
                errors=[
                    {
                        "field": ".".join(map(str, error["loc"])),
                        "type": error["type"],
                    }
                    for error in exc.errors(include_input=False, include_url=False)
                ],
            )
            return self._validated(result)

        if call.name == "search_learning_history":
            data = self._search(params.query, params.limit)
        elif call.name == "read_learning_history":
            record = self._records.get(params.source_ref)
            if record is None:
                result["error_code"] = "source_unavailable"
                return self._validated(result)
            data = self._read(record, params.offset, params.limit)
        elif call.name == "get_knowledge_context":
            data = deepcopy(self.snapshot.knowledge_context)
        elif call.name == "get_learner_profile":
            data = {
                **deepcopy(self.snapshot.learner_profile),
                "knowledge_state": deepcopy(self.snapshot.knowledge_state),
                "memories": deepcopy(self.snapshot.stable_memories),
            }
        else:
            data = {"items": deepcopy(self.snapshot.review_queue)}

        data, output_truncated = self._bounded_data(data, spec.output_limit)
        # 搜索项仅用于发现；只有读取原文成功后才通过 source_refs 升级为可引用来源。
        refs = []
        if (
            call.name == "read_learning_history"
            and data.get("source_ref") in self._verified_source_refs
        ):
            refs = [data["source_ref"]]
        result.update(
            status="empty" if data.get("items") == [] else "ok",
            data=data,
            source_refs=refs,
            truncated=bool(data.get("truncated", False) or output_truncated),
            next_cursor=data.get("next_cursor"),
        )
        return self._validated(result)

    def _search(self, query: str, limit: int) -> dict[str, Any]:
        needle = query.casefold()
        items = []
        for record in self.snapshot.history_records:
            haystack = " ".join((
                record.source_ref,
                record.role,
                record.knowledge_id or "",
                record.content,
            )).casefold()
            if needle and needle not in haystack:
                continue
            items.append({
                "source_ref": record.source_ref,
                "role": record.role,
                "recorded_at": record.recorded_at.isoformat(),
                "knowledge_id": record.knowledge_id,
                "excerpt": record.content[:400],
                "discovery_only": True,
                "citation_status": (
                    "verified"
                    if record.source_ref in self._verified_source_refs
                    else "unread_candidate"
                ),
            })
            if len(items) >= limit:
                break
        return {
            "items": items,
            "bounded": True,
            "citable_without_read": False,
        }

    def _read(self, record: HistoryRecord, offset: int, limit: int) -> dict[str, Any]:
        content = record.content[offset : offset + limit]
        end = offset + len(content)
        truncated = end < len(record.content)
        self._read_ranges.setdefault(record.source_ref, []).append((offset, end))
        merged_end = 0
        for start, stop in sorted(self._read_ranges[record.source_ref]):
            if start > merged_end:
                break
            merged_end = max(merged_end, stop)
        if merged_end >= len(record.content):
            self._verified_source_refs.add(record.source_ref)
        return {
            "source_ref": record.source_ref,
            "role": record.role,
            "recorded_at": record.recorded_at.isoformat(),
            "knowledge_id": record.knowledge_id,
            "content": content,
            "truncated": truncated,
            "next_cursor": end if truncated else None,
        }

    @staticmethod
    def _result() -> dict[str, Any]:
        return {
            "status": "denied",
            "data": {},
            "source_refs": [],
            "error_code": None,
            "retryable": False,
            "truncated": False,
            "next_cursor": None,
            "cached": False,
            "errors": [],
        }

    @staticmethod
    def _bounded_data(data: dict[str, Any], limit: int) -> tuple[dict[str, Any], bool]:
        if _json_bytes(data) <= limit:
            return data, False
        bounded = deepcopy(data)
        for field in (
            "items",
            "memories",
            "knowledge_states",
            "prerequisite_context",
        ):
            values = bounded.get(field)
            if isinstance(values, list):
                while values and _json_bytes(bounded) > limit:
                    values.pop()
        if _json_bytes(bounded) > limit:
            bounded = {"message": "结果过长，请缩小范围或分页读取。"}
        return bounded, True

    @staticmethod
    def _validated(result: dict[str, Any]) -> dict[str, Any]:
        return ToolResult.model_validate(result).model_dump()

"""评测样例、单例结果和汇总报告的数据契约。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.versions import APP_VERSION, EVAL_SCHEMA_VERSION, TRACE_SCHEMA_VERSION


EvalKind = Literal[
    "tutor_response",
    "harness_contract",
    "trace_contract",
    "labeled_response",
]


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    license: str = Field(min_length=1)
    source_id: str | None = None
    revision: str | None = None
    split: str | None = None


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    suite: str = Field(min_length=1, max_length=64)
    kind: EvalKind
    knowledge_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    source: SourceMetadata

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: int) -> int:
        if value != EVAL_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported eval schema {value}; expected {EVAL_SCHEMA_VERSION}"
            )
        return value

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("tags must be unique")
        return value


class ScoreDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scorer: str
    passed: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    message: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)


class EvalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    suite: str
    kind: EvalKind
    tags: list[str]
    passed: bool
    score: float = Field(ge=0, le=1)
    details: list[ScoreDetail]
    observed: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = Field(ge=0)


class EvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = EVAL_SCHEMA_VERSION
    app_version: str = APP_VERSION
    trace_schema_version: int = TRACE_SCHEMA_VERSION
    suite: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    dataset_revision: str
    provider: str
    model: str
    generation_mode: str
    config_fingerprint: str
    total: int
    passed: int
    failed: int
    pass_rate: float = Field(ge=0, le=1)
    tag_metrics: dict[str, dict[str, float | int]]
    results: list[EvalResult]

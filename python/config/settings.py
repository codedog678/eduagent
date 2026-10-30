"""Application settings loaded from environment variables and .env."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
LLM_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "MINIMAX_API_KEY",
    "DEEPSEEK_API_KEY",
    "LLM_PROVIDER",
)


def _env_file_has_llm_config() -> bool:
    if not ENV_FILE.exists():
        return False

    try:
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in LLM_ENV_KEYS and value.strip():
                return True
    except OSError:
        return False

    return False


class Settings(BaseSettings):
    llm_provider: Literal["auto", "template", "anthropic", "openai", "minimax", "deepseek"] = "auto"
    anthropic_api_key: str = Field(default="", repr=False)
    anthropic_base_url: str = "https://api.anthropic.com"
    model_id: str = "claude-3-sonnet-20240229"

    openai_api_key: str = Field(default="", repr=False)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    minimax_api_key: str = Field(default="", repr=False)
    minimax_model: str = "MiniMax-M2.7"

    deepseek_api_key: str = Field(default="", repr=False)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_thinking: Literal["enabled", "disabled"] = "disabled"
    deepseek_reasoning_effort: Literal["high", "max"] = "high"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent"
    redis_url: str = "redis://localhost:6379/0"

    distributed_enabled: bool = False
    distributed_database_url: str = ""
    distributed_redis_url: str = "redis://localhost:6379/1"
    distributed_stream: str = "eduagent:runs"
    distributed_consumer_group: str = "eduagent-run-workers"
    distributed_worker_id: str = ""
    distributed_lease_seconds: float = Field(default=15, ge=3, le=300)
    distributed_heartbeat_seconds: float = Field(default=3, ge=.5, le=60)
    distributed_poll_block_ms: int = Field(default=1000, ge=10, le=60000)
    distributed_max_attempts: int = Field(default=3, ge=1, le=20)
    distributed_outbox_batch_size: int = Field(default=50, ge=1, le=500)
    distributed_demo_pause_before_commit_seconds: float = Field(
        default=0, ge=0, le=300
    )
    distributed_experts_enabled: bool = False
    expert_stream: str = "eduagent:experts"
    expert_consumer_group: str = "eduagent-expert-workers"
    expert_lease_seconds: float = Field(default=15, ge=3, le=300)
    expert_heartbeat_seconds: float = Field(default=3, ge=.5, le=60)
    expert_poll_block_ms: int = Field(default=1000, ge=10, le=60000)
    expert_max_job_seconds: float = Field(default=120, ge=1, le=3600)
    expert_max_payload_bytes: int = Field(default=262144, ge=1024, le=10485760)
    expert_queued_payload_bytes_limit: int = Field(
        default=10485760, ge=1024, le=1073741824
    )
    expert_queued_limit_per_role: int = Field(default=50, ge=1, le=10000)
    expert_running_limit_per_role: int = Field(default=2, ge=1, le=1000)
    expert_retry_base_seconds: float = Field(default=1, gt=0, le=300)
    expert_retry_max_seconds: float = Field(default=30, gt=0, le=3600)
    expert_result_poll_seconds: float = Field(default=.25, gt=0, le=60)
    expert_demo_pause_before_result_seconds: float = Field(
        default=0, ge=0, le=300
    )
    otel_exporter_otlp_endpoint: str = ""

    api_port: int = 8888
    log_level: str = "INFO"

    enable_db_logging: bool = True
    enable_agent_llm_decisions: bool = False
    llm_timeout_seconds: float = 12.0
    llm_max_concurrency: int = Field(default=4, ge=1, le=256)
    llm_queue_timeout_seconds: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    harness_store_path: str = str(PROJECT_ROOT / "data" / "harness.sqlite3")
    harness_timeout_seconds: float = Field(default=45.0, gt=0)
    harness_queue_timeout_seconds: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    harness_max_steps: int = Field(default=64, gt=0, le=1000)
    quiz_ttl_seconds: float = Field(default=86400, gt=0)
    enable_tutor_tools: bool = True
    tutor_max_model_calls: int = Field(default=3, gt=0, le=10)
    tutor_max_tool_calls: int = Field(default=4, gt=0, le=20)
    tutor_context_budget_tokens: int = Field(default=6000, ge=2000, le=32000)
    tutor_max_output_tokens: int = Field(default=800, ge=100, le=2000)
    tutor_handler_timeout_seconds: float = Field(default=40, gt=0)
    memory_retrieval_mode: Literal["lexical", "hybrid"] = "hybrid"
    memory_embedding_provider: Literal["siliconflow"] = "siliconflow"
    memory_embedding_model: str = "BAAI/bge-m3"
    memory_embedding_base_url: str = "https://api.siliconflow.cn/v1"
    memory_embedding_api_key: str = Field(default="", repr=False)
    siliconflow_api_key: str = Field(default="", repr=False)
    memory_embedding_timeout_seconds: float = Field(default=8, gt=0)
    memory_semantic_threshold: float = Field(default=0.55, ge=-1, le=1)
    memory_vector_limit: int = Field(default=2000, ge=20, le=20000)
    memory_worker_enabled: bool = True
    memory_worker_interval_seconds: float = Field(default=5, gt=0)
    memory_episode_message_threshold: int = Field(default=6, ge=2, le=100)
    memory_extraction_enabled: bool = True
    memory_rerank_enabled: bool = False
    memory_rerank_model: str = "BAAI/bge-reranker-v2-m3"
    memory_rerank_base_url: str = "https://api.siliconflow.cn/v1"
    memory_rerank_api_key: str = Field(default="", repr=False)
    enable_coordinator: bool = True
    policy_registry_path: str = ""
    policy_loading_enabled: bool = False
    policy_auto_rollback_enabled: bool = False
    policy_health_window: int = Field(default=50, ge=1)
    policy_health_min_samples: int = Field(default=20, ge=1)
    policy_commit_failure_rate: float = Field(default=.1, gt=0, le=1)
    coordinator_max_model_calls: int = Field(default=8, ge=3, le=16)
    coordinator_max_tool_calls: int = Field(default=16, ge=4, le=40)
    coordinator_max_delegations: int = Field(default=3, ge=1, le=6)
    coordinator_max_replans: int = Field(default=1, ge=0, le=1)
    specialist_max_model_calls: int = Field(default=3, ge=1, le=6)
    specialist_max_tool_calls: int = Field(default=4, ge=1, le=10)
    coordinator_tutor_model_reserve: int = Field(default=2, ge=1, le=4)
    coordinator_tutor_tool_reserve: int = Field(default=3, ge=1, le=8)

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("llm_provider", "deepseek_thinking", "deepseek_reasoning_effort", mode="before")
    @classmethod
    def normalize_model_options(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_selected_provider_key(self) -> "Settings":
        if self.llm_provider not in {"auto", "template"}:
            if not getattr(self, f"{self.llm_provider}_api_key").strip():
                raise ValueError(f"{self.llm_provider.upper()}_API_KEY is required for LLM_PROVIDER")
        if self.distributed_experts_enabled and not self.distributed_enabled:
            raise ValueError("distributed experts require distributed run plane")
        if self.distributed_experts_enabled:
            if self.expert_heartbeat_seconds >= self.expert_lease_seconds / 2:
                raise ValueError("expert heartbeat must be less than half the lease")
            if self.expert_retry_base_seconds > self.expert_retry_max_seconds:
                raise ValueError("expert retry base must not exceed retry maximum")
            if self.expert_max_payload_bytes > self.expert_queued_payload_bytes_limit:
                raise ValueError(
                    "expert payload maximum must not exceed queued payload limit"
                )
        if self.distributed_enabled:
            database_url = self.effective_distributed_database_url
            if not database_url:
                raise ValueError("distributed database URL is required")
            if not database_url.startswith("postgresql+asyncpg://"):
                raise ValueError(
                    "distributed database URL must use postgresql+asyncpg"
                )
            if (
                self.distributed_heartbeat_seconds
                >= self.distributed_lease_seconds / 2
            ):
                raise ValueError(
                    "DISTRIBUTED_HEARTBEAT_SECONDS must be less than half the lease"
                )
        return self

    @field_validator(
        "database_url",
        "distributed_database_url",
        mode="before",
    )
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        if value.startswith("postgresql+asyncpg://"):
            return value
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        return value

    @property
    def effective_distributed_database_url(self) -> str:
        return self.distributed_database_url or self.database_url

    @property
    def llm_config_source(self) -> str:
        if any(os.getenv(key) for key in LLM_ENV_KEYS):
            return "env"
        if _env_file_has_llm_config():
            return ".env"
        return "none"

    @property
    def configured_llm_provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        if self.minimax_api_key:
            return "minimax"
        if self.deepseek_api_key:
            return "deepseek"
        return "template"

    @property
    def configured_llm_model(self) -> str:
        if self.configured_llm_provider == "anthropic":
            return self.model_id
        if self.configured_llm_provider == "openai":
            return self.openai_model
        if self.configured_llm_provider == "minimax":
            return self.minimax_model
        if self.configured_llm_provider == "deepseek":
            return self.deepseek_model
        return "template"

    @property
    def llm_enabled(self) -> bool:
        return self.configured_llm_provider != "template"


settings = Settings()

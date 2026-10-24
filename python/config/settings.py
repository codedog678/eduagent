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

    api_port: int = 8888
    log_level: str = "INFO"

    enable_db_logging: bool = True
    enable_agent_llm_decisions: bool = False
    llm_timeout_seconds: float = 12.0
    harness_store_path: str = str(PROJECT_ROOT / "data" / "harness.sqlite3")
    harness_timeout_seconds: float = Field(default=45.0, gt=0)
    harness_max_steps: int = Field(default=64, gt=0, le=1000)
    quiz_ttl_seconds: float = Field(default=86400, gt=0)
    enable_tutor_tools: bool = True
    tutor_max_model_calls: int = Field(default=3, gt=0, le=10)
    tutor_max_tool_calls: int = Field(default=4, gt=0, le=20)
    tutor_context_budget_tokens: int = Field(default=6000, ge=2000, le=32000)
    tutor_max_output_tokens: int = Field(default=800, ge=100, le=2000)
    tutor_handler_timeout_seconds: float = Field(default=40, gt=0)

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
        return self

    @field_validator("database_url", mode="before")
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

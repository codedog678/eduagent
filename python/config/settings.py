"""Application settings loaded from environment variables and .env."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
LLM_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "MINIMAX_API_KEY",
    "DEEPSEEK_API_KEY",
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
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    model_id: str = "claude-3-sonnet-20240229"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    minimax_api_key: str = ""
    minimax_model: str = "MiniMax-M2.7"

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent"
    redis_url: str = "redis://localhost:6379/0"

    api_port: int = 8888
    log_level: str = "INFO"

    enable_db_logging: bool = True
    enable_agent_llm_decisions: bool = False
    llm_timeout_seconds: float = 12.0

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def llm_config_source(self) -> str:
        if any(os.getenv(key) for key in LLM_ENV_KEYS):
            return "env"
        if _env_file_has_llm_config():
            return ".env"
        return "none"

    @property
    def configured_llm_provider(self) -> str:
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

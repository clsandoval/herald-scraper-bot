"""Nested `pydantic-settings` for daimon-core. Constructed via `load_settings()`.

Never import a module-level settings singleton — callers construct once at the
edge (CLI entrypoint, test fixture) and inject downstream.

Phase 1 trim: only the sections needed to boot Postgres + Discord + Anthropic
Managed Agents (kept per D-09) are present. Multi-tenant/MCP/Slack/CLI/billing/
GitHub-OAuth/crypto/notebook/Sentry sections from the daimon fork are dropped —
this repo has no multi-tenant, MCP, Slack, or billing surface (D-04).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, HttpUrl, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    url: PostgresDsn
    test_url: PostgresDsn | None = None


class AnthropicSettings(BaseModel):
    api_key: SecretStr
    base_url: HttpUrl = HttpUrl("https://api.anthropic.com")


class DiscordSettings(BaseModel):
    """Discord adapter config (adapter package added in a later plan).

    Optional so non-Discord contexts (e.g. this test config module) keep
    working. Kept minimal for Phase 1 — max_concurrent_turns_per_tenant and
    per_caller_thread_sessions are Phase 6+ multi-tenant concerns, dropped here.
    """

    bot_token: SecretStr
    health_port: int = 8081
    """Port for the liveness responder served by the discord entrypoint.

    Env: DAIMON_DISCORD__HEALTH_PORT.
    """


class LogSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class Settings(BaseSettings):
    database: DatabaseSettings
    anthropic: AnthropicSettings
    discord: DiscordSettings | None = None
    log: LogSettings = LogSettings()

    model_config = SettingsConfigDict(
        env_prefix="DAIMON_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_settings(*, _env_file: str | None = ".env") -> Settings:
    """Construct a `Settings` from the live process env + optional `.env` file.

    `_env_file` exists to give tests a way to disable `.env` loading
    (`_env_file=None`) so they only see `monkeypatch.setenv` values.
    """
    return Settings(_env_file=_env_file)  # pyright: ignore[reportCallIssue]

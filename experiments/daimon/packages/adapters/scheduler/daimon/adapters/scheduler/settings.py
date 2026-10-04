"""SchedulerSettings — adapter-local config (env prefix DAIMON_SCHEDULER__).

Kept on the adapter so core `Settings` stays clean of adapter-specific
fields (matches `DiscordSettings`'s boundary). Copied verbatim from the
daimon fork — self-contained `BaseSettings`, no dependency on trimmed core
config sections.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SchedulerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DAIMON_SCHEDULER__",
        env_nested_delimiter="__",
        extra="ignore",
    )

    tick_interval_s: float = 30.0
    """Seconds between scheduler ticks (loop sleep)."""

    max_age_s: float = 900.0
    """Freshness window — rows whose `next_fire_at` slipped past
    `now - max_age_s` are advanced via `advance_stale` and not fired."""

    max_concurrent_fires: int = 10
    """Global cap on simultaneously-dispatched fires within one tick.
    Env: DAIMON_SCHEDULER__MAX_CONCURRENT_FIRES."""

    dispatch_timeout_s: float = 600.0
    """Per-fire wall-clock deadline (asyncio.wait_for) guarding hung
    connections. Env: DAIMON_SCHEDULER__DISPATCH_TIMEOUT_S."""

    advisory_lock_key: int = 0x44_41_49_4D_4F_4E_53_43
    """Postgres `pg_try_advisory_lock` int64 key. Default = ascii `DAIMONSC`.
    Two scheduler processes share the key; the second exits cleanly."""

    health_port: int = 8082
    """Port for the stdlib liveness responder (Fly health check). Must NOT
    collide with discord's 8081 on a shared Fly VM."""

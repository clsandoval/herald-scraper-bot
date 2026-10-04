"""DiscordRuntime -- DI bundle for the Discord adapter process.

Trimmed from daimon's `runtime.py`: no billing_config, notebook_rate_limiter,
resolver_cache, or deployment_default -- those are multi-tenant/MA-provisioning
concerns excluded by D-04. Phase 1's `pong` reply doesn't touch the DB or
Anthropic; `sessionmaker`/`anthropic` are wired here (per D-09, MA stays in the
dependency graph) but have no Phase-1 caller.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from anthropic import AsyncAnthropic
from daimon.core.config import Settings
from daimon.core.db import build_engine, build_session_factory
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True)
class DiscordRuntime:
    settings: Settings
    anthropic: AsyncAnthropic
    sessionmaker: async_sessionmaker[AsyncSession]


@asynccontextmanager
async def build_runtime(settings: Settings) -> AsyncIterator[DiscordRuntime]:
    engine = build_engine(str(settings.database.url))
    sessionmaker = build_session_factory(engine)
    async with AsyncAnthropic(
        api_key=settings.anthropic.api_key.get_secret_value(),
        base_url=str(settings.anthropic.base_url),
    ) as anthropic:
        try:
            yield DiscordRuntime(
                settings=settings,
                anthropic=anthropic,
                sessionmaker=sessionmaker,
            )
        finally:
            await engine.dispose()

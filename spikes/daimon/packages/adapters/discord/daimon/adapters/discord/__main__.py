"""``python -m daimon.adapters.discord`` entrypoint.

Adapted from daimon's `__main__.py`: the Sentry/observability init block is
dropped entirely (no `daimon.core.observability`/`sentry-sdk` in this fork --
see 01-01-SUMMARY.md's dependency trim). Everything else -- settings load,
liveness responder, signal-safe bot lifecycle -- is kept.
"""

from __future__ import annotations

import asyncio
import sys

import discord
import structlog
from daimon.adapters.discord.bot import HeraldBot
from daimon.adapters.discord.runtime import build_runtime
from daimon.core.config import load_settings
from daimon.core.health import start_liveness_responder
from daimon.core.logging_setup import configure_log_level

log = structlog.get_logger()


async def main() -> None:
    settings = load_settings()
    if settings.discord is None:
        log.info("discord adapter disabled", reason="no bot token")
        sys.exit(0)
    # Configure the JSON log chain BEFORE the first log line so it takes effect.
    configure_log_level(settings.log.level)
    async with build_runtime(settings) as runtime:
        intents = discord.Intents.default()
        intents.message_content = True
        bot = HeraldBot(runtime=runtime, intents=intents)
        # Liveness responder shares this loop with the Discord client (health.py's
        # documented co-location property) -- a hung loop fails the Fly check.
        health_server = await start_liveness_responder(settings.discord.health_port)
        log.info("starting_discord_bot")
        try:
            await bot.start(settings.discord.bot_token.get_secret_value())
        finally:
            health_server.close()
            await health_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())

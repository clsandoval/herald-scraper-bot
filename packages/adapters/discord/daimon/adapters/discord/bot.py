"""HeraldBot -- the thinnest Discord adapter that boots.

Phase 1 has no query/SQL agent, no scoring, no MA turn invocation (D-09 keeps
the MA wiring in `runtime.py`, but nothing calls it yet). `on_message` exists
purely to prove the round-trip: Discord gateway connects, a mention is
detected, a reply is sent. This ALSO establishes DISC-01 ("never posts
unprompted") at the code level -- the bot never reacts to a message it was
not explicitly mentioned in.

Not built by trimming daimon's 1,170-line `bot.py` (see 01-RESEARCH.md
Pitfall/Anti-Pattern: trimming in place risks orphaned imports across a dozen
interdependent files) -- written fresh, following daimon's `on_message`
dispatch shape only.
"""

from __future__ import annotations

import discord
import structlog

from daimon.adapters.discord.runtime import DiscordRuntime

log = structlog.get_logger()


class HeraldBot(discord.Client):
    """Minimal Discord client: reply `pong` iff explicitly @mentioned."""

    def __init__(self, *, runtime: DiscordRuntime, intents: discord.Intents) -> None:
        super().__init__(intents=intents)
        self.runtime = runtime

    async def on_ready(self) -> None:
        log.info("discord_ready", user=str(self.user))

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            # Ignore our own messages -- never react to ourselves.
            return
        if self.user not in message.mentions:
            # DISC-01: never post unprompted -- only reply when @mentioned.
            return
        await message.channel.send("pong")

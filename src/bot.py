"""Unified Herald Discord bot with periodic reporting and interactive analysis."""

import discord
from discord.ext import commands, tasks
import asyncio
import logging
import openai
from datetime import datetime, timezone

from .config import Config
from .cache.match_cache import UnifiedMatchCache
from .commands.ask_command import AskCommandCog
from .herald_reporter import HeraldMatchReporter

logger = logging.getLogger(__name__)


class UnifiedHeraldBot(commands.Bot):
    """Production Herald bot with integrated periodic and interactive features."""

    def __init__(self, config: Config):
        # Discord intents
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            # Performance optimizations
            chunk_guilds_at_startup=False,
            member_cache_flags=discord.MemberCacheFlags.none(),
        )

        self.config = config
        self.start_time = datetime.now(timezone.utc)

        # Unified cache shared between periodic and interactive features
        self.match_cache = UnifiedMatchCache(
            ttl_hours=config.cache_ttl_hours, max_entries=config.cache_max_entries
        )

        # Herald reporter for periodic tasks
        self.herald_reporter = HeraldMatchReporter(config, self.match_cache)

        # OpenAI client for interactive analysis
        if config.has_openai:
            self.openai_client = openai.AsyncOpenAI(
                api_key=config.openai_api_key,
                timeout=config.openai_timeout_seconds,
                max_retries=config.openai_max_retries,
            )
            logger.info("OpenAI client initialized for interactive features")
        else:
            self.openai_client = None
            logger.warning(
                "OpenAI API key not provided - interactive features disabled"
            )

        # Basic tracking
        self.stats = {"errors": 0}

    async def setup_hook(self):
        """Initialize bot components and commands."""
        logger.info("Setting up unified Herald bot...")

        try:
            # Load interactive commands if OpenAI is available
            if self.openai_client:
                await self.add_cog(
                    AskCommandCog(
                        self, self.config, self.match_cache, self.openai_client
                    )
                )
                logger.info("Interactive analysis commands loaded")

            # Sync slash commands in development
            if self.config.discord_test_channel_id:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")

        except Exception as e:
            logger.error(f"Setup hook failed: {e}")
            raise

    @property
    def uptime(self):
        """Get bot uptime as timedelta."""
        return datetime.now(timezone.utc) - self.start_time

    async def on_ready(self):
        """Bot ready event - start background tasks."""
        logger.info(
            f"Herald bot ready! Connected as {self.user} (startup time: {self.uptime.total_seconds():.1f}s)"
        )

        # Start herald reporting task (staggered to avoid startup conflicts)
        await asyncio.sleep(5)  # Wait 1 minute after startup
        self.herald_reporting_task.start()

    @tasks.loop(hours=24)
    async def herald_reporting_task(self):
        """Periodic Herald match discovery and posting."""
        try:
            logger.info("Starting periodic Herald match discovery...")
            await self.herald_reporter.run_periodic_report(self)
            logger.info("Periodic Herald report completed successfully")

        except Exception as e:
            logger.error(f"Periodic Herald report failed: {e}")
            self.stats["errors"] += 1

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        """Handle slash command errors gracefully."""
        self.stats["errors"] += 1
        logger.error(f"Slash command error: {error}")

        if interaction.response.is_done():
            await interaction.followup.send(
                f"❌ Command failed: {str(error)[:100]}", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Command failed: {str(error)[:100]}", ephemeral=True
            )

    @herald_reporting_task.before_loop
    async def before_herald_reporting(self):
        """Wait for bot ready before starting periodic reports."""
        await self.wait_until_ready()

    async def close(self):
        """Graceful shutdown."""
        try:
            uptime = datetime.now(timezone.utc) - self.start_time

            logger.info(f"Herald bot shutting down after {uptime}")
            logger.info(f"Final statistics: {self.stats}")

            # Cancel background tasks
            self.herald_reporting_task.cancel()

            # Close OpenAI client
            if self.openai_client:
                await self.openai_client.close()

        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        finally:
            await super().close()

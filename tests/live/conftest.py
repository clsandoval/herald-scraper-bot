"""Live test fixtures for real Discord bot testing."""
import pytest
import pytest_asyncio
import discord
from discord.ext import commands
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

from src.config import Config
from src.bot import UnifiedHeraldBot

# Load environment variables for live testing
load_dotenv()


@pytest.fixture
def live_config():
    """Live configuration using real environment variables."""
    config = Config.from_env()
    
    # Validate required environment variables for live testing
    if not config.discord_bot_token or config.discord_bot_token.startswith("TEST_"):
        pytest.skip("Live Discord testing requires real DISCORD_BOT_TOKEN")
    
    if not config.discord_test_channel_id:
        pytest.skip("Live Discord testing requires DISCORD_TEST_CHANNEL_ID")
    
    return config


@pytest_asyncio.fixture
async def live_discord_bot(live_config):
    """Real Discord bot instance for live testing."""
    bot = UnifiedHeraldBot(live_config)
    
    try:
        # Start bot and wait for ready
        bot_task = asyncio.create_task(bot.start(live_config.discord_bot_token))
        
        # Wait for bot to be ready (max 30 seconds)
        ready_timeout = 30
        start_time = datetime.now()
        
        while not bot.is_ready():
            if (datetime.now() - start_time).seconds > ready_timeout:
                raise TimeoutError("Bot failed to connect within 30 seconds")
            await asyncio.sleep(0.5)
        
        yield bot
        
    finally:
        # Clean shutdown
        await bot.close()
        try:
            bot_task.cancel()
            await bot_task
        except asyncio.CancelledError:
            pass


@pytest_asyncio.fixture
async def live_test_channel(live_discord_bot, live_config):
    """Get the live test channel."""
    channel = live_discord_bot.get_channel(live_config.discord_test_channel_id)
    
    if not channel:
        pytest.skip(f"Test channel {live_config.discord_test_channel_id} not accessible")
    
    if not isinstance(channel, discord.TextChannel):
        pytest.skip(f"Test channel {live_config.discord_test_channel_id} is not a text channel")
    
    # Verify bot has permissions
    permissions = channel.permissions_for(channel.guild.me)
    required_perms = ['send_messages', 'create_public_threads', 'send_messages_in_threads']
    
    missing_perms = [perm for perm in required_perms if not getattr(permissions, perm, False)]
    if missing_perms:
        pytest.skip(f"Bot missing permissions in test channel: {missing_perms}")
    
    return channel


@pytest_asyncio.fixture
async def test_cleanup():
    """Track test messages/threads for cleanup."""
    cleanup_items = []
    
    def add_for_cleanup(item):
        cleanup_items.append(item)
    
    yield add_for_cleanup
    
    # Cleanup after test
    for item in cleanup_items:
        try:
            if hasattr(item, 'delete'):
                await item.delete()
        except (discord.NotFound, discord.Forbidden):
            pass  # Already deleted or no permissions
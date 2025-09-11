"""Discord channel and thread management utilities."""
import discord
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


async def get_verified_channels(bot, channel_ids: List[int]) -> List[discord.TextChannel]:
    """Get accessible Discord channels from IDs."""
    channels = []
    for channel_id in channel_ids:
        try:
            channel = bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                # Test permissions
                if channel.permissions_for(channel.guild.me).send_messages:
                    channels.append(channel)
                    logger.info(f"Added verified channel: {channel.name}")
                else:
                    logger.warning(f"No send permissions for channel: {channel.name}")
            else:
                logger.error(f"Channel {channel_id} not found or not a text channel")
        except Exception as e:
            logger.error(f"Failed to access channel {channel_id}: {e}")
    
    return channels


async def create_match_thread(channel: discord.TextChannel, match_embed: discord.Embed, 
                            match_id: int, match_date: datetime) -> Optional[discord.Thread]:
    """Create a match discussion thread with summary embed."""
    try:
        # Create thread name with match info
        thread_name = f"Match {match_id} - {match_date.strftime('%Y-%m-%d')}"
        
        # Send the match summary embed first
        message = await channel.send(embed=match_embed)
        
        # Create thread from the message
        thread = await message.create_thread(
            name=thread_name,
            auto_archive_duration=1440  # 24 hours
        )
        
        logger.info(f"Created match thread: {thread_name}")
        return thread
        
    except Exception as e:
        logger.error(f"Failed to create match thread for {match_id}: {e}")
        return None


async def cleanup_old_threads(channel: discord.TextChannel, retention_days: int) -> None:
    """Clean up old match threads beyond retention period."""
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cleaned_count = 0
        
        # Get all threads in the channel
        async for thread in channel.archived_threads(limit=None):
            if thread.created_at < cutoff_date and "Match" in thread.name:
                try:
                    await thread.delete()
                    cleaned_count += 1
                    logger.info(f"Deleted old thread: {thread.name}")
                    # Rate limit thread deletions
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Failed to delete thread {thread.name}: {e}")
        
        # Also check active threads
        for thread in channel.threads:
            if thread.created_at < cutoff_date and "Match" in thread.name:
                try:
                    await thread.delete()
                    cleaned_count += 1
                    logger.info(f"Deleted old active thread: {thread.name}")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Failed to delete active thread {thread.name}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old match threads from {channel.name}")
            
    except Exception as e:
        logger.error(f"Failed to cleanup threads in {channel.name}: {e}")
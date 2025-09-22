"""Unified Herald match reporting with cache integration."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from .config import Config
from .api.opendota import OpenDotaClient
from .api.stratz import StratzClient
from .discord.embeds import create_match_summary_embed, create_team_analysis_embed
from .discord.channels import get_verified_channels, create_match_thread, cleanup_old_threads
from .cache.match_cache import UnifiedMatchCache

logger = logging.getLogger(__name__)


class HeraldMatchReporter:
    """Unified Herald match reporter with cache integration."""
    
    def __init__(self, config: Config, cache: UnifiedMatchCache):
        self.config = config
        self.cache = cache
        self.opendota_client = OpenDotaClient(config)
        self.stratz_client = StratzClient(config)
        
    async def run_periodic_report(self, bot) -> None:
        """Execute periodic Herald match discovery and reporting."""
        logger.info("Starting periodic Herald match report...")
        
        try:
            # Get accessible Discord channels
            channel_ids = [self.config.discord_test_channel_id]
            channels = await get_verified_channels(bot, channel_ids)
            
            if not channels:
                logger.error("No accessible Discord channels found")
                return
            
            # Clean up old threads first
            for channel in channels:
                await cleanup_old_threads(channel, self.config.thread_retention_days)
            
            # Discover Herald matches
            herald_matches = await self.opendota_client.discover_herald_matches()
            
            if not herald_matches:
                logger.info("No new Herald matches found")
                return
            
            logger.info(f"Processing {len(herald_matches)} Herald matches for posting...")
            
            # Process each match with cache integration
            posted_count = 0
            for match in herald_matches:
                try:
                    success = await self._process_and_post_match(match.match_id, channels)
                    if success:
                        posted_count += 1
                    
                    # Rate limiting between matches
                    await asyncio.sleep(self.config.api_delay_seconds * 2)
                    
                except Exception as e:
                    logger.error(f"Failed to process match {match.match_id}: {e}")
                    continue
            
            logger.info(f"Periodic report completed: {posted_count}/{len(herald_matches)} matches posted")
            
        except Exception as e:
            logger.error(f"Periodic report failed: {e}")
            raise
    
    async def _process_and_post_match(self, match_id: int, channels: List) -> bool:
        """Process single match and post to Discord channels."""
        logger.info(f"Processing match {match_id}")
        
        try:
            # Check if already cached (avoid duplicate processing)
            cached_data = await self.cache.get(match_id)
            if cached_data:
                match_details, stratz_data = cached_data
                logger.info(f"Using cached data for match {match_id} (periodic report)")
            else:
                # Fetch fresh data
                match_details = await self.opendota_client.get_match_details(match_id)
                
                # Skip matches with leavers
                if match_details.has_leavers:
                    logger.info(f"Match {match_id} has leavers, skipping")
                    return False
                
                # Rate limiting before Stratz call
                await asyncio.sleep(self.config.api_delay_seconds)
                
                # Get enhanced player data
                stratz_data = await self.stratz_client.get_match_analysis(match_id)
                
                # Validate Herald players
                if not self.stratz_client.validate_herald_match(stratz_data):
                    logger.info(f"Match {match_id} contains non-Herald players, skipping")
                    return False
                
                # Cache for future ask commands
                await self.cache.set(match_id, match_details, stratz_data)
                logger.info(f"Cached match data for {match_id}")
            
            # Fetch win/loss data for all players
            player_wl_data = await self._fetch_player_win_loss(match_details, stratz_data)

            # Create Discord embeds
            match_embed = create_match_summary_embed(match_details, stratz_data)
            radiant_embed = create_team_analysis_embed(stratz_data.radiant_players, True, player_wl_data)
            dire_embed = create_team_analysis_embed(stratz_data.dire_players, False, player_wl_data)
            
            # Post to all channels
            success = True
            for channel in channels:
                try:
                    # Create match discussion thread
                    match_date = datetime.fromtimestamp(match_details.start_time, tz=timezone.utc)
                    thread = await create_match_thread(channel, match_embed, match_id, match_date)
                    
                    if thread:
                        # Post team analysis to thread
                        await thread.send(embed=radiant_embed)
                        await asyncio.sleep(1)  # Rate limiting
                        await thread.send(embed=dire_embed)
                        
                        # Add helpful message about ask command
                        await asyncio.sleep(1)
                        help_message = (
                            "💡 **Tip:** Use `/ask` in this thread to get AI-powered analysis! "
                            "Try questions like:\n"
                            "• `Why did this match last so long?`\n"
                            "• `What were the key mistakes?`\n"
                            "• `How could the losing team have won?`"
                        )
                        await thread.send(help_message)
                        
                        logger.info(f"Successfully posted match {match_id} to {channel.name}")
                    else:
                        success = False
                        
                except Exception as e:
                    logger.error(f"Failed to post match {match_id} to channel {channel.name}: {e}")
                    success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing match {match_id}: {e}")
            return False

    async def _fetch_player_win_loss(self, match_details, stratz_data):
        """Fetch win/loss data for all players in the match.

        Returns a dictionary mapping hero_id to (wins, losses) tuples.
        """
        player_wl_map = {}

        try:
            # Create a mapping of hero_id to account_id from OpenDota data
            hero_to_account = {}
            for player in match_details.players:
                hero_id = player.get("hero_id")
                account_id = player.get("account_id")
                if hero_id and account_id:
                    hero_to_account[hero_id] = account_id

            # Fetch win/loss data for all accounts concurrently
            wl_tasks = []
            hero_ids = []
            for hero_id, account_id in hero_to_account.items():
                wl_tasks.append(self.opendota_client.get_player_wl(account_id))
                hero_ids.append(hero_id)

            if wl_tasks:
                wl_results = await asyncio.gather(*wl_tasks, return_exceptions=True)

                # Map results back to hero_ids
                for hero_id, wl_result in zip(hero_ids, wl_results):
                    if isinstance(wl_result, tuple):
                        player_wl_map[hero_id] = wl_result
                    elif isinstance(wl_result, Exception):
                        logger.warning(f"Failed to fetch W/L for hero_id {hero_id}: {wl_result}")
                    # If None, player is anonymous or request failed

            logger.info(f"Fetched W/L data for {len(player_wl_map)} players")

        except Exception as e:
            logger.error(f"Error fetching player W/L data: {e}")

        return player_wl_map
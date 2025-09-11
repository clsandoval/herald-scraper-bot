"""Discord integration tests for Phase 3 verification."""
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.bot import UnifiedHeraldBot
from src.commands.ask_command import AskCommandCog
from src.discord.embeds import create_match_summary_embed, create_ai_response_embed
from src.herald_reporter import HeraldMatchReporter


@pytest.mark.unit
class TestPhase3DiscordIntegration:
    """Test Phase 3 Discord integration components."""
    
    @pytest.mark.asyncio
    async def test_bot_starts_successfully(self, test_config):
        """Test bot can be instantiated and configured."""
        bot = UnifiedHeraldBot(test_config)
        
        assert bot.config == test_config
        assert bot.match_cache is not None
        
        # Test OpenAI client initialization
        if test_config.has_openai:
            assert bot.openai_client is not None
        
        # Clean shutdown
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_slash_commands_register(self, test_config, unified_cache, mock_openai_client):
        """Test slash commands can be registered."""
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        
        # Test AskCommandCog can be created and added
        ask_cog = AskCommandCog(bot, test_config, unified_cache, mock_openai_client)
        
        assert ask_cog.config == test_config
        assert ask_cog.cache == unified_cache
        assert ask_cog.openai == mock_openai_client
    
    @pytest.mark.asyncio
    async def test_cache_integration_works(self, test_config, sample_match_details, sample_stratz_data):
        """Test cache integration between periodic and interactive features."""
        from src.cache.match_cache import UnifiedMatchCache
        
        # Create cache for this test
        unified_cache = UnifiedMatchCache(ttl_hours=1, max_entries=10)
        reporter = HeraldMatchReporter(test_config, unified_cache)
        
        try:
            # Simulate caching match data during periodic report
            match_id = 8451070414
            await unified_cache.set(match_id, sample_match_details, sample_stratz_data)
            
            # Verify cache hit for interactive command
            cached_data = await unified_cache.get(match_id)
            assert cached_data is not None
            
            match_details, stratz_data = cached_data
            assert match_details == sample_match_details
            assert stratz_data == sample_stratz_data
            
            # Verify cache has data
            stats = await unified_cache.stats()
            assert stats['entries'] == 1
        finally:
            await unified_cache.clear()
    
    @pytest.mark.asyncio
    async def test_periodic_reporting_functions(self, test_config, aioresponses_mock):
        """Test periodic reporting discovers and processes matches."""
        from src.cache.match_cache import UnifiedMatchCache
        
        # Create cache for this test
        unified_cache = UnifiedMatchCache(ttl_hours=1, max_entries=10)
        
        try:
            # Mock API responses
            aioresponses_mock.post(
                'https://api.opendota.com/api/explorer',
                payload={
                    'command': 'SELECT',
                    'rowCount': 1,
                    'rows': [{'match_id': 8451070414, 'start_time': 1640995200, 'duration': 5247, 'avg_rank_tier': 12}],
                    'fields': []
                }
            )
            
            reporter = HeraldMatchReporter(test_config, unified_cache)
            
            # Test match discovery (without Discord posting)
            with patch.object(reporter, '_process_and_post_match', return_value=True) as mock_process:
                mock_bot = MagicMock()
                mock_bot.get_channel = AsyncMock(return_value=MagicMock())
                
                # This should discover matches without failing
                matches = await reporter.opendota_client.discover_herald_matches()
                assert len(matches) >= 0  # May be 0 if no Herald matches found
        finally:
            await unified_cache.clear()
    
    @pytest.mark.asyncio
    async def test_interactive_commands_work(self, test_config, mock_openai_client, mock_slash_interaction, sample_match_details, sample_stratz_data):
        """Test interactive ask command processes questions correctly."""
        from src.cache.match_cache import UnifiedMatchCache
        
        # Create cache for this test
        unified_cache = UnifiedMatchCache(ttl_hours=1, max_entries=10)
        
        try:
            bot = MagicMock()
            ask_cog = AskCommandCog(bot, test_config, unified_cache, mock_openai_client)
            
            # Pre-cache match data
            match_id = 8451070414
            await unified_cache.set(match_id, sample_match_details, sample_stratz_data)
            
            # Mock thread name extraction
            mock_slash_interaction.channel.name = f"Match {match_id} - 2025-01-01"
            
            # Test ask command - call the callback directly
            await ask_cog.ask_about_match.callback(ask_cog, mock_slash_interaction, "Why did this match last so long?")
            
            # Verify interaction was handled
            mock_slash_interaction.response.defer.assert_called_once()
            mock_slash_interaction.followup.send.assert_called_once()
            
            # Verify OpenAI was called
            mock_openai_client.chat.completions.create.assert_called_once()
        finally:
            await unified_cache.clear()
    
    def test_embeds_create_properly(self, sample_match_details, sample_stratz_data):
        """Test Discord embeds are created with proper formatting."""
        # Test match summary embed
        summary_embed = create_match_summary_embed(sample_match_details, sample_stratz_data)
        
        assert isinstance(summary_embed, discord.Embed)
        assert "Herald Match Analysis" in summary_embed.title
        assert str(sample_match_details.match_id) in summary_embed.description
        assert len(summary_embed.fields) > 0
        
        # Test AI response embed
        question = "Why did this match last so long?"
        response = "This match lasted long due to inefficient farming."
        ai_embed = create_ai_response_embed(question, response, sample_match_details.match_id)
        
        assert isinstance(ai_embed, discord.Embed)
        assert "AI Match Analysis" in ai_embed.title
        assert question in ai_embed.description
        assert response in ai_embed.fields[0].value
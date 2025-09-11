"""Foundation tests for Phase 1 verification."""
import pytest
import asyncio
from src.config import Config
from src.cache.match_cache import UnifiedMatchCache
from src.models import OpenDotaMatch, StratzPlayer


@pytest.mark.unit
class TestPhase1Foundation:
    """Test Phase 1 foundation components."""
    
    def test_configuration_loads_from_env(self, monkeypatch):
        """Test configuration loads from environment variables."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
        monkeypatch.setenv("DISCORD_TEST_CHANNEL_ID", "123456789")
        monkeypatch.setenv("OPENDOTA_API_KEY", "test_key")
        monkeypatch.setenv("STRATZ_API_TOKEN", "test_token")
        
        config = Config.from_env()
        config.validate_required()
        
        assert config.discord_bot_token == "test_token"
        assert config.discord_test_channel_id == 123456789
    
    def test_models_validate_real_api_data(self, real_api_fixtures):
        """Test models validate real API response data."""
        # Test OpenDota match validation
        from src.models.opendota import OpenDotaMatchDetail
        match_data = real_api_fixtures['opendota_match']
        match_detail = OpenDotaMatchDetail(**match_data)
        assert match_detail.match_id > 0
        assert match_detail.duration > 0
        
        # Test Stratz player validation
        from src.models.stratz import StratzPlayer
        stratz_data = real_api_fixtures['stratz_graphql']
        players_data = stratz_data['data']['match']['players']
        for player_data in players_data:
            player = StratzPlayer(**player_data)
            assert player.kills >= 0
            assert player.deaths >= 0
    
    @pytest.mark.asyncio
    async def test_cache_operations_work_correctly(self):
        """Test cache operations function properly."""
        cache = UnifiedMatchCache(ttl_hours=1, max_entries=10)
        
        # Test stats on empty cache
        stats = await cache.stats()
        assert stats['entries'] == 0
        
        # Test basic cache operations
        await cache.set(123, "match_details", "stratz_data")
        cached_data = await cache.get(123)
        
        assert cached_data is not None
        assert cached_data[0] == "match_details"
        assert cached_data[1] == "stratz_data"
    
    def test_all_imports_resolve(self):
        """Test all core imports resolve correctly."""
        from src.models import OpenDotaMatch, StratzPlayer
        from src.config import Config
        from src.cache.match_cache import UnifiedMatchCache
        
        # Verify classes can be instantiated
        assert OpenDotaMatch
        assert StratzPlayer
        assert Config
        assert UnifiedMatchCache
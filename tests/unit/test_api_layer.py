"""API layer tests for Phase 2 verification."""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta
import aioresponses

from src.api.opendota import OpenDotaClient
from src.api.stratz import StratzClient
from src.constants import get_hero_name, get_item_name, is_herald_rank
from src.config import Config


@pytest.mark.unit
class TestPhase2APILayer:
    """Test Phase 2 API layer components."""
    
    def test_api_clients_import_correctly(self):
        """Test API clients can be imported and instantiated."""
        from src.api.opendota import OpenDotaClient
        from src.api.stratz import StratzClient
        
        config = Config(
            discord_bot_token="test",
            discord_test_channel_id=1234567890123456789,
            opendota_api_key="test",
            stratz_api_token="test"
        )
        
        opendota_client = OpenDotaClient(config)
        stratz_client = StratzClient(config)
        
        assert opendota_client.config == config
        assert stratz_client.config == config
    
    def test_constants_load_completely(self):
        """Test game constants provide expected mappings."""
        from src.constants import get_hero_name, get_item_name, is_herald_rank
        
        # Test hero mappings (using actual IDs from our mapping)
        assert get_hero_name(1) == "Anti-Mage"
        assert get_hero_name(2) == "Axe"
        assert get_hero_name(999999) == "Unknown Hero (999999)"  # Fallback
        
        # Test item mappings
        assert get_item_name(1) == "Blink Dagger"
        assert get_item_name(0) == "Empty"
        assert get_item_name(None) == "Empty"
        
        # Test rank validation
        assert is_herald_rank(11) is True  # Herald I
        assert is_herald_rank(15) is True  # Herald V
        assert is_herald_rank(10) is False # Below Herald
        assert is_herald_rank(16) is False # Above Herald
        assert is_herald_rank(None) is False
    
    @pytest.mark.asyncio
    async def test_models_validate_api_responses(self, real_api_fixtures):
        """Test models correctly validate real API response data."""
        from src.models.opendota import OpenDotaQueryResponse, OpenDotaMatchDetail
        from src.models.stratz import StratzMatchResponse
        
        # Test OpenDota query response
        query_response = OpenDotaQueryResponse(**real_api_fixtures['opendota_query'])
        matches = query_response.to_matches()
        assert len(matches) > 0
        assert all(match.match_id > 0 for match in matches)
        
        # Test OpenDota match details
        match_detail = OpenDotaMatchDetail(**real_api_fixtures['opendota_match'])
        assert match_detail.duration > 0
        assert len(match_detail.players) == 10
        
        # Test Stratz response
        stratz_response = StratzMatchResponse(**real_api_fixtures['stratz_graphql'])
        match_data = stratz_response.to_match_data(8451070414)
        assert len(match_data.players) == 10
    
    @pytest.mark.asyncio
    async def test_rate_limiting_works(self, test_config, aioresponses_mock):
        """Test API clients respect rate limiting."""
        # Mock successful API responses
        aioresponses_mock.post(
            'https://api.opendota.com/api/explorer',
            payload={'command': 'SELECT', 'rowCount': 0, 'rows': [], 'fields': []}
        )
        
        client = OpenDotaClient(test_config)
        
        # Test rate limiting between chunks
        start_time = datetime.now()
        
        # Mock time chunks to have just 2 chunks
        with patch.object(client, '_generate_time_chunks', return_value=[
            (1640995200, 1640998800),
            (1640998800, 1641002400)
        ]):
            await client.discover_herald_matches()
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        # Should have at least one delay between chunks
        assert elapsed >= test_config.api_delay_seconds
    
    @pytest.mark.asyncio
    async def test_error_handling_provides_actionable_messages(self, test_config, aioresponses_mock):
        """Test error handling provides helpful error messages."""
        # Mock API error response
        aioresponses_mock.get(
            'https://api.opendota.com/api/matches/12345',
            status=404
        )
        
        client = OpenDotaClient(test_config)
        
        with pytest.raises(ValueError) as exc_info:
            await client.get_match_details(12345)
        
        error_msg = str(exc_info.value)
        assert "404" in error_msg
        assert "12345" in error_msg
        assert "OpenDota API error" in error_msg
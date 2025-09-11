"""Comprehensive test fixtures for unified Herald bot testing."""
import pytest
import pytest_asyncio
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
import aioresponses

from src.config import Config
from src.models.opendota import OpenDotaMatch, OpenDotaMatchDetail
from src.models.stratz import StratzMatchData, StratzPlayer
from src.cache.match_cache import UnifiedMatchCache

# Load real API response fixtures
FIXTURES_DIR = Path(__file__).parent.parent
API_FIXTURES = {}

try:
    API_FIXTURES.update({
        'opendota_query': json.loads((FIXTURES_DIR / 'truths/api/opendota_query_response.json').read_text()),
        'opendota_match': json.loads((FIXTURES_DIR / 'truths/api/opendota_match_details_response.json').read_text()),
        'stratz_graphql': json.loads((FIXTURES_DIR / 'truths/api/stratz_graphql_response.json').read_text())
    })
except FileNotFoundError as e:
    pytest.skip(f"API fixture file not found: {e}", allow_module_level=True)


@pytest.fixture
def test_config():
    """Test configuration with safe defaults."""
    return Config(
        discord_bot_token="TEST_BOT_TOKEN_12345",
        discord_test_channel_id=1234567890123456789,
        discord_test_thread_id=1234567890123456790,
        opendota_api_key="TEST_OPENDOTA_KEY",
        stratz_api_token="TEST_STRATZ_TOKEN",
        openai_api_key="TEST_OPENAI_KEY",
        # Performance settings for fast tests
        query_days_back=1,
        api_delay_seconds=0,
        thread_retention_days=1,
        cache_ttl_hours=1,
        cache_max_entries=10
    )


@pytest.fixture
def real_api_fixtures():
    """Real API response data for validation."""
    return API_FIXTURES


@pytest_asyncio.fixture
async def unified_cache():
    """Unified cache instance for testing.""" 
    cache = UnifiedMatchCache(ttl_hours=1, max_entries=10)
    yield cache
    await cache.clear()


@pytest.fixture
def sample_herald_match():
    """Herald match based on real API data."""
    return OpenDotaMatch(
        match_id=8451070414,  # Real match ID
        start_time=int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()),
        duration=5247,  # Real duration from fixture
        avg_rank_tier=14,  # Herald IV
        lobby_type=7,
        game_mode=22
    )


@pytest.fixture  
def sample_match_details():
    """Sample match details based on real API data."""
    return OpenDotaMatchDetail(
        match_id=8451070414,
        duration=4524,
        start_time=1757252569,
        lobby_type=7,
        game_mode=22,
        radiant_win=True,
        players=[
            {"player_slot": 0, "hero_id": 26, "kills": 6, "deaths": 19, "leaver_status": 0},
            {"player_slot": 1, "hero_id": 52, "kills": 8, "deaths": 14, "leaver_status": 0},
            {"player_slot": 2, "hero_id": 93, "kills": 12, "deaths": 18, "leaver_status": 0},
            {"player_slot": 3, "hero_id": 31, "kills": 10, "deaths": 17, "leaver_status": 0},
            {"player_slot": 4, "hero_id": 7, "kills": 4, "deaths": 21, "leaver_status": 0},
            {"player_slot": 128, "hero_id": 2, "kills": 22, "deaths": 8, "leaver_status": 0},
            {"player_slot": 129, "hero_id": 6, "kills": 13, "deaths": 10, "leaver_status": 0},
            {"player_slot": 130, "hero_id": 41, "kills": 7, "deaths": 11, "leaver_status": 0},
            {"player_slot": 131, "hero_id": 45, "kills": 6, "deaths": 12, "leaver_status": 0},
            {"player_slot": 132, "hero_id": 21, "kills": 8, "deaths": 9, "leaver_status": 0}
        ]
    )


@pytest.fixture
def sample_stratz_data():
    """Sample Stratz data for testing."""
    # Create sample players with Herald ranks
    radiant_players = [
        StratzPlayer(
            heroId=26, kills=6, deaths=19, assists=36, level=29,
            heroDamage=15000, isRadiant=True, position="POSITION_1",
            steamAccount={"seasonRank": 14}, stats={"actionsPerMinute": [45, 50, 55]}
        ),
        StratzPlayer(
            heroId=52, kills=8, deaths=14, assists=32, level=26,
            heroDamage=18000, isRadiant=True, position="POSITION_2",
            steamAccount={"seasonRank": 13}, stats={"actionsPerMinute": [48, 52, 58]}
        ),
        StratzPlayer(
            heroId=93, kills=12, deaths=18, assists=28, level=25,
            heroDamage=22000, isRadiant=True, position="POSITION_3",
            steamAccount={"seasonRank": 15}, stats={"actionsPerMinute": [42, 47, 53]}
        ),
        StratzPlayer(
            heroId=31, kills=10, deaths=17, assists=34, level=24,
            heroDamage=12000, isRadiant=True, position="POSITION_4",
            steamAccount={"seasonRank": 11}, stats={"actionsPerMinute": [40, 45, 50]}
        ),
        StratzPlayer(
            heroId=7, kills=4, deaths=21, assists=40, level=22,
            heroDamage=8000, isRadiant=True, position="POSITION_5",
            steamAccount={"seasonRank": 12}, stats={"actionsPerMinute": [38, 42, 48]}
        )
    ]
    
    dire_players = [
        StratzPlayer(
            heroId=2, kills=22, deaths=8, assists=18, level=30,
            heroDamage=28000, isRadiant=False, position="POSITION_1",
            steamAccount={"seasonRank": 15}, stats={"actionsPerMinute": [55, 60, 65]}
        ),
        StratzPlayer(
            heroId=6, kills=13, deaths=10, assists=25, level=28,
            heroDamage=24000, isRadiant=False, position="POSITION_2",
            steamAccount={"seasonRank": 14}, stats={"actionsPerMinute": [52, 57, 62]}
        ),
        StratzPlayer(
            heroId=41, kills=7, deaths=11, assists=30, level=26,
            heroDamage=16000, isRadiant=False, position="POSITION_3",
            steamAccount={"seasonRank": 13}, stats={"actionsPerMinute": [48, 52, 58]}
        ),
        StratzPlayer(
            heroId=45, kills=6, deaths=12, assists=35, level=25,
            heroDamage=11000, isRadiant=False, position="POSITION_4",
            steamAccount={"seasonRank": 12}, stats={"actionsPerMinute": [45, 50, 55]}
        ),
        StratzPlayer(
            heroId=21, kills=8, deaths=9, assists=32, level=23,
            heroDamage=9000, isRadiant=False, position="POSITION_5",
            steamAccount={"seasonRank": 11}, stats={"actionsPerMinute": [43, 47, 52]}
        )
    ]
    
    all_players = radiant_players + dire_players
    
    return StratzMatchData(
        match_id=8451070414,
        players=all_players
    )


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is a test AI response about the Herald match."
    
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def mock_slash_interaction():
    """Mock Discord slash command interaction."""
    import discord
    
    mock_interaction = MagicMock()
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()
    
    # Mock thread channel properly - needs to be instance of discord.Thread
    mock_thread = MagicMock(spec=discord.Thread)
    mock_thread.name = "Match 8451070414 - 2025-01-01"
    mock_interaction.channel = mock_thread
    
    return mock_interaction


@pytest.fixture
def aioresponses_mock():
    """Mock for aiohttp responses."""
    with aioresponses.aioresponses() as m:
        yield m
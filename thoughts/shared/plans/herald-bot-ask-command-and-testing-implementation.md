# Herald Discord Bot Ask Command and Testing Implementation Plan

## Overview

Extend the Herald Discord Bot with an interactive ask slash command for OpenAI-powered match analysis and implement comprehensive testing infrastructure with extensive validation coverage. This builds on the existing 4-phase implementation plan while adding modern Discord slash commands and robust testing patterns.

## Current State Analysis

### What Exists Now
- **src/**: Empty implementation - `main.py` is completely blank, ready for clean implementation
- **deprecated/**: Fully functional Discord bot with comprehensive API integrations, Discord posting, thread management
- **Comprehensive Implementation Plan**: Detailed 4-phase plan with Pydantic models and pure functions architecture
- **API Response Samples**: Real OpenDota and Stratz response data for validation (`opendota_query_response.json`, `stratz_graphql_response.json`)
- **Testing Infrastructure**: Excellent pytest configuration with coverage, async support, comprehensive markers but **zero actual test files**

### Key Discoveries:
- `deprecated/functions.py:366-413` - Mature Stratz GraphQL integration with Bearer token authentication
- `deprecated/constants.py:1-649` - Complete hero/item mappings ready for reuse
- `pytest.ini:11-16` - Well-configured testing with coverage reporting and async support
- `requirements-test.txt:4-25` - Complete testing dependencies available but not integrated
- `deprecated/discord_bot.py:199-221` - Multi-channel posting patterns with individual error handling

## Desired End State

A production-ready Discord bot that:
1. **Maintains existing functionality** - Periodic Herald match discovery and posting
2. **Responds to slash commands** - Modern `/ask` command for interactive match analysis
3. **Provides AI-powered analysis** - OpenAI integration for match commentary and Q&A
4. **Caches match data intelligently** - In-memory cache to reduce API calls for repeated questions
5. **Has comprehensive test coverage** - Extensive unit, integration, and E2E tests with validation
6. **Supports live Discord testing** - Real bot posting verification for development confidence

### Verification Method
- Bot responds to `/ask` slash command in match threads with relevant OpenAI analysis
- Cache reduces API calls by 80% for repeated questions about same match
- Test suite achieves 90%+ coverage with validation of all API integrations
- Live Discord tests verify actual slash command functionality
- All existing periodic posting functionality remains working

## What We're NOT Doing

- AI commentary generation for periodic posts (focus on ask command first)
- Database persistence (maintain stateless pattern with in-memory cache)
- Rate limiting for OpenAI calls (ignore for now per research findings)
- Multiple bot instances - single bot with both periodic tasks and commands
- Migration of deprecated/ code - build fresh implementation following existing plan

## Implementation Approach

**Extend Existing Architecture**: Build on the planned 4-phase pure functions approach while adding interactive slash command capabilities.

**Comprehensive Testing First**: Implement complete testing infrastructure before major features to ensure reliability.

**Reuse Mature Patterns**: Leverage existing API integration patterns from deprecated/ while modernizing with Pydantic validation.

## Phase 1: Foundation Enhancement & Testing Infrastructure

### Overview
Establish missing dependencies, comprehensive testing framework, and OpenAI integration foundation.

### Changes Required:

#### 1. Dependency Updates
**File**: `pyproject.toml`
**Changes**: Add missing critical dependencies

```toml
# Add to dependencies
pydantic = "^2.11.7"
openai = "^1.58.1"  # Already present, verify version

# Move test dependencies from requirements-test.txt to dev group
[dependency-groups]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0", 
    "pytest-mock>=3.11.0",
    "aioresponses>=0.7.4",
    "freezegun>=1.2.2",
    "pytest-xdist>=3.3.0",
    "pytest-html>=4.1.1",
    "factory-boy>=3.3.0"
]
```

#### 2. Testing Infrastructure Foundation
**File**: `tests/conftest.py`
**Changes**: Create comprehensive test fixtures and setup

```python
"""Test fixtures and configuration for Herald Discord Bot."""
import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import aioresponses

from src.config import Config
from src.models.opendota import OpenDotaMatch, OpenDotaMatchDetail
from src.models.stratz import StratzMatchData, StratzPlayer

# Load real API response samples for validation
FIXTURES_DIR = Path(__file__).parent.parent
API_SAMPLES = {
    'opendota_query': json.loads((FIXTURES_DIR / 'opendota_query_response.json').read_text()),
    'opendota_match': json.loads((FIXTURES_DIR / 'opendota_match_details_response.json').read_text()),
    'stratz_graphql': json.loads((FIXTURES_DIR / 'stratz_graphql_response.json').read_text())
}

@pytest.fixture
def test_config():
    """Test configuration with safe defaults."""
    return Config(
        discord_bot_token="TEST_TOKEN_12345",
        discord_test_channel_id=1234567890,
        discord_test_thread_id=1234567891,
        opendota_api_key="TEST_OPENDOTA_KEY",
        stratz_api_token="TEST_STRATZ_TOKEN",
        openai_api_key="TEST_OPENAI_KEY",
        query_days_back=1,
        api_delay_seconds=0,  # No delays in tests
        thread_retention_days=1
    )

@pytest.fixture
def real_api_responses():
    """Real API response data for validation testing."""
    return API_SAMPLES

@pytest.fixture
def sample_herald_match():
    """Sample Herald match data from real API responses."""
    return OpenDotaMatch(
        match_id=8451070414,  # Real match ID from API samples
        start_time=int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()),
        duration=5247,  # Real duration from sample
        avg_rank_tier=12,  # Herald rank
    )

@pytest.fixture
def sample_stratz_data(real_api_responses):
    """Sample Stratz match data with Herald players."""
    # Use real Stratz response structure but ensure Herald ranks
    raw_data = real_api_responses['stratz_graphql']['data']['match']
    
    # Modify player ranks to be Herald for testing
    for player in raw_data['players']:
        if player.get('steamAccount') and player['steamAccount'].get('seasonRank'):
            player['steamAccount']['seasonRank'] = min(15, player['steamAccount']['seasonRank'])
    
    return StratzMatchData(match_id=8451070414, **raw_data)

@pytest.fixture
def mock_discord_bot(test_config):
    """Mock Discord bot for testing."""
    bot = MagicMock()
    bot.config = test_config
    bot.get_channel = AsyncMock()
    bot.fetch_channel = AsyncMock()
    return bot

@pytest.fixture  
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = AsyncMock()
    
    # Mock chat completion response
    mock_response = AsyncMock()
    mock_choice = AsyncMock()
    mock_message = AsyncMock()
    mock_message.content = "This is a test AI response about the Herald match."
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    
    client.chat.completions.create = AsyncMock(return_value=mock_response)
    return client

@pytest.fixture
def mock_discord_thread():
    """Mock Discord thread for slash command testing.""" 
    thread = AsyncMock()
    thread.id = 1234567891
    thread.name = "Match 8451070414 - 2025-01-01"  # Standard format
    return thread

@pytest.fixture
def mock_slash_context(mock_discord_thread):
    """Mock Discord slash command interaction context."""
    ctx = AsyncMock()
    ctx.channel = mock_discord_thread
    ctx.response = AsyncMock()
    ctx.followup = AsyncMock()
    return ctx

@pytest.fixture
def aioresponses_mock():
    """HTTP mocking for API calls."""
    with aioresponses.aioresponses() as m:
        yield m
```

#### 3. Test Markers Configuration
**File**: `pytest.ini`
**Changes**: Add comprehensive test markers

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=src
    --cov-report=term-missing
    --cov-report=html:htmlcov
markers =
    unit: Unit tests for individual components
    integration: Integration tests for API interactions
    e2e: End-to-end tests with real Discord verification  
    discord: Tests requiring Discord bot functionality
    live_api: Tests requiring real API credentials
    performance: Performance and load testing
    error_scenarios: Error handling and edge case testing
    openai: Tests requiring OpenAI API integration
    cache: Tests for in-memory caching functionality
    slash_commands: Tests for Discord slash command functionality

asyncio_mode = auto
```

#### 4. Makefile for Easy Test Execution
**File**: `Makefile`
**Changes**: Create comprehensive test execution targets

```makefile
.PHONY: test test-unit test-integration test-e2e test-quick test-coverage test-openai

# Quick development testing
test-quick:
	uv run python -m pytest tests/unit/ -x -v

# Comprehensive testing
test-unit:
	uv run python -m pytest tests/unit/ -v -m unit

test-integration:
	uv run python -m pytest tests/integration/ -v -m integration

test-e2e:
	uv run python -m pytest tests/e2e/ -v -m "e2e and not live_api"

test-live:
	uv run python -m pytest tests/e2e/ -v -m live_api

test-openai:
	uv run python -m pytest -v -m openai

test-cache:
	uv run python -m pytest -v -m cache

test-slash:
	uv run python -m pytest -v -m slash_commands

# Coverage reporting
test-coverage:
	uv run python -m pytest --cov=src --cov-report=html --cov-report=term tests/

# Run all non-live tests
test: test-unit test-integration test-e2e

# Install dependencies
install:
	uv sync --all-groups

# Linting
lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/
```

### Success Criteria:

#### Automated Verification:
- [ ] Dependencies install cleanly: `uv sync --all-groups`
- [ ] Test infrastructure imports without errors: `uv run python -c "from tests.conftest import test_config, real_api_responses"`
- [ ] Pytest discovers test structure: `uv run python -m pytest --collect-only`
- [ ] Coverage reporting works: `make test-coverage` 
- [ ] All test markers validate: `uv run python -m pytest --strict-markers --collect-only`

#### Manual Verification:
- [ ] Real API response fixtures load correctly and contain expected Herald match data
- [ ] Mock fixtures provide realistic Discord bot and OpenAI client behavior
- [ ] Test execution is fast and provides clear feedback
- [ ] Coverage reports highlight areas needing tests
- [ ] Makefile targets work on both development and CI environments

---

## Phase 2: Ask Slash Command Implementation

### Overview
Implement the interactive ask slash command with OpenAI integration, match ID extraction, and in-memory caching.

### Changes Required:

#### 1. In-Memory Match Cache
**File**: `src/cache/match_cache.py`
**Changes**: Simple cache implementation for match data

```python
"""In-memory cache for Herald match data."""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Single cache entry with TTL."""
    data: Any
    created_at: datetime
    access_count: int = 0
    
    @property
    def is_expired(self, ttl_hours: int = 2) -> bool:
        """Check if entry is expired."""
        return datetime.utcnow() - self.created_at > timedelta(hours=ttl_hours)
    
    def access(self) -> Any:
        """Mark as accessed and return data."""
        self.access_count += 1
        return self.data

class MatchDataCache:
    """In-memory cache for match data with automatic cleanup."""
    
    def __init__(self, ttl_hours: int = 2, max_entries: int = 100):
        self.ttl_hours = ttl_hours
        self.max_entries = max_entries
        self._cache: Dict[int, CacheEntry] = {}
        self._lock = asyncio.Lock()
        
    async def get(self, match_id: int) -> Optional[Tuple[Any, Any]]:
        """Get cached match data (match_details, stratz_data) if available."""
        async with self._lock:
            entry = self._cache.get(match_id)
            if entry and not entry.is_expired(self.ttl_hours):
                logger.info(f"Cache hit for match {match_id} (accessed {entry.access_count} times)")
                return entry.access()
            elif entry:
                # Remove expired entry
                del self._cache[match_id]
                logger.info(f"Removed expired cache entry for match {match_id}")
            
            return None
    
    async def set(self, match_id: int, match_details: Any, stratz_data: Any):
        """Cache match data with automatic cleanup if needed."""
        async with self._lock:
            # Cleanup if at capacity
            if len(self._cache) >= self.max_entries:
                await self._cleanup_expired()
                
                # If still at capacity, remove oldest
                if len(self._cache) >= self.max_entries:
                    oldest_id = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
                    del self._cache[oldest_id]
                    logger.info(f"Evicted oldest cache entry: match {oldest_id}")
            
            self._cache[match_id] = CacheEntry(
                data=(match_details, stratz_data),
                created_at=datetime.utcnow()
            )
            logger.info(f"Cached match data for match {match_id}")
    
    async def _cleanup_expired(self):
        """Remove all expired entries."""
        expired_keys = [
            match_id for match_id, entry in self._cache.items()
            if entry.is_expired(self.ttl_hours)
        ]
        for match_id in expired_keys:
            del self._cache[match_id]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    async def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total_accesses = sum(entry.access_count for entry in self._cache.values())
            return {
                "entries": len(self._cache),
                "total_accesses": total_accesses,
                "average_accesses": total_accesses / len(self._cache) if self._cache else 0,
                "oldest_entry": min(
                    (entry.created_at for entry in self._cache.values()),
                    default=None
                )
            }
```

#### 2. Ask Slash Command Implementation
**File**: `src/commands/ask_command.py`
**Changes**: Discord slash command with OpenAI integration

```python
"""Ask slash command for Herald match analysis."""
import discord
from discord.ext import commands
from discord import app_commands
import re
import logging
from typing import Optional

from ..api.opendota import get_match_details
from ..api.stratz import get_match_analysis  
from ..cache.match_cache import MatchDataCache
from ..config import Config

logger = logging.getLogger(__name__)

class AskCommandCog(commands.Cog):
    """Slash commands for Herald match analysis."""
    
    def __init__(self, bot: commands.Bot, config: Config, cache: MatchDataCache, openai_client):
        self.bot = bot
        self.config = config
        self.cache = cache
        self.openai = openai_client
        
    @app_commands.command(name="ask", description="Ask questions about the Herald match in this thread")
    @app_commands.describe(question="Your question about the match analysis")
    async def ask_about_match(self, interaction: discord.Interaction, question: str):
        """Ask AI questions about Herald match data."""
        
        # Defer response since API calls may take time
        await interaction.response.defer()
        
        try:
            # Verify we're in a match thread
            if not isinstance(interaction.channel, discord.Thread):
                await interaction.followup.send("❌ This command only works in Herald match threads.", ephemeral=True)
                return
                
            # Extract match ID from thread name
            match_id = self._extract_match_id(interaction.channel.name)
            if not match_id:
                await interaction.followup.send("❌ Could not find match ID in thread name.", ephemeral=True)
                return
                
            logger.info(f"Processing ask command for match {match_id}: {question[:50]}...")
            
            # Try cache first
            cached_data = await self.cache.get(match_id)
            if cached_data:
                match_details, stratz_data = cached_data
                logger.info(f"Using cached data for match {match_id}")
            else:
                # Fetch fresh data
                logger.info(f"Fetching fresh data for match {match_id}")
                match_details = await get_match_details(self.config, match_id)
                
                # Add delay between API calls
                await asyncio.sleep(self.config.api_delay_seconds)
                
                stratz_data = await get_match_analysis(self.config, match_id)
                
                # Cache the results
                await self.cache.set(match_id, match_details, stratz_data)
            
            # Generate OpenAI response
            response_text = await self._generate_ai_response(match_id, match_details, stratz_data, question)
            
            # Send response (truncate if too long)
            if len(response_text) > 2000:
                response_text = response_text[:1997] + "..."
                
            await interaction.followup.send(response_text)
            
        except Exception as e:
            logger.error(f"Error processing ask command: {e}")
            await interaction.followup.send(f"❌ Failed to analyze match: {str(e)[:100]}", ephemeral=True)
    
    def _extract_match_id(self, thread_name: str) -> Optional[int]:
        """Extract match ID from thread name pattern: 'Match 8451070414 - 2025-01-01'."""
        match = re.search(r'Match (\d+)', thread_name)
        if match:
            return int(match.group(1))
        return None
    
    async def _generate_ai_response(self, match_id: int, match_details, stratz_data, question: str) -> str:
        """Generate OpenAI response with full match context."""
        
        # Format duration 
        duration_min = match_details.duration // 60
        duration_sec = match_details.duration % 60
        
        # Create comprehensive prompt with full match data
        prompt = f"""You are analyzing a Herald-tier Dota 2 match. Provide helpful insights focused on Herald-level gameplay.

Match {match_id}:
Duration: {duration_min}:{duration_sec:02d}
Average Rank: Herald (all players are Herald tier)

COMPLETE MATCH DATA:
OpenDota Details: {match_details.dict()}

Stratz Player Data: {stratz_data.dict()}

User Question: {question}

Instructions:
- Answer specifically about this match data
- Focus on Herald-level gameplay insights  
- Be concise but helpful (under 400 words)
- Reference specific player actions, items, or stats when relevant
- Explain "why" things happened, not just "what" happened

Answer:"""

        response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content

    @app_commands.command(name="cache-stats", description="Show match data cache statistics")
    async def cache_stats(self, interaction: discord.Interaction):
        """Display cache performance statistics."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return
            
        stats = await self.cache.stats()
        
        embed = discord.Embed(
            title="📊 Match Data Cache Stats", 
            color=0x00FF00,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="Cached Entries", value=str(stats["entries"]), inline=True)
        embed.add_field(name="Total Accesses", value=str(stats["total_accesses"]), inline=True) 
        embed.add_field(name="Avg Accesses", value=f"{stats['average_accesses']:.1f}", inline=True)
        
        if stats["oldest_entry"]:
            embed.add_field(name="Oldest Entry", value=stats["oldest_entry"].strftime("%Y-%m-%d %H:%M"), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    # This will be called by bot.load_extension()
    pass
```

#### 3. Bot Integration with Slash Commands
**File**: `src/bot.py`
**Changes**: Update bot to include slash commands and caching

```python
"""Herald Discord bot with slash command support."""
import discord
from discord.ext import commands, tasks
import asyncio
import logging
import openai

from .config import Config
from .cache.match_cache import MatchDataCache
from .commands.ask_command import AskCommandCog
from .herald_reporter import run_herald_report

logger = logging.getLogger(__name__)

class HeraldBot(commands.Bot):
    """Discord bot for Herald match analysis with interactive commands."""
    
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",  # Keep for backward compatibility
            intents=intents,
            help_command=None  # Disable default help command
        )
        
        self.config = config
        self.match_cache = MatchDataCache(ttl_hours=2, max_entries=50)
        
        # Initialize OpenAI client
        if config.openai_api_key:
            self.openai_client = openai.AsyncOpenAI(api_key=config.openai_api_key)
        else:
            logger.warning("OpenAI API key not provided - ask command will not work")
            self.openai_client = None
        
    async def setup_hook(self):
        """Setup hook called when bot is ready."""
        logger.info("Bot is setting up...")
        
        # Add slash command cog
        if self.openai_client:
            await self.add_cog(AskCommandCog(self, self.config, self.match_cache, self.openai_client))
            logger.info("Ask command cog loaded successfully")
        
        # Sync slash commands (only in development - remove in production)
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
        
    async def on_ready(self):
        """Called when bot connects to Discord."""
        logger.info(f"Bot connected as {self.user} to {len(self.guilds)} guilds")
        
        # Start periodic herald reporting
        self.herald_report_task.start()
        
    @tasks.loop(hours=24)
    async def herald_report_task(self):
        """Periodic task to check for Herald matches."""
        try:
            await run_herald_report(self, self.config)
            logger.info("Herald report task completed successfully")
        except Exception as e:
            logger.error(f"Herald report task failed: {e}")
        
    @herald_report_task.before_loop
    async def before_herald_report(self):
        """Wait until bot is ready before starting periodic task."""
        await self.wait_until_ready()
        
    async def close(self):
        """Cleanup when bot shuts down."""
        self.herald_report_task.cancel()
        await super().close()
```

### Success Criteria:

#### Automated Verification:
- [ ] All imports resolve: `uv run python -c "from src.commands.ask_command import AskCommandCog; from src.cache.match_cache import MatchDataCache"`
- [ ] Bot loads without errors: `uv run python -c "from src.bot import HeraldBot; from src.config import Config; bot = HeraldBot(Config.from_env())"`
- [ ] Cache operations work: `uv run python -c "import asyncio; from src.cache.match_cache import MatchDataCache; asyncio.run(MatchDataCache().stats())"`
- [ ] OpenAI integration initializes: `uv run python -c "import openai; openai.AsyncOpenAI(api_key='test')"`

#### Manual Verification:
- [ ] `/ask` slash command appears in Discord after bot startup and sync
- [ ] Cache reduces API calls - same match queried twice should show cache hit in logs
- [ ] Match ID extraction works for thread names like "Match 8451070414 - 2025-01-01"
- [ ] OpenAI responses are relevant and under 400 words
- [ ] Error handling provides user-friendly messages for edge cases
- [ ] `/cache-stats` command shows meaningful statistics to administrators

---

## Phase 3: Comprehensive Testing Suite Implementation  

### Overview
Implement extensive testing coverage with unit tests, integration tests, and end-to-end validation including live Discord verification.

### Changes Required:

#### 1. Unit Tests for Core Components
**File**: `tests/unit/test_ask_command.py`
**Changes**: Comprehensive unit tests for ask command logic

```python
"""Unit tests for ask slash command functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from src.commands.ask_command import AskCommandCog
from src.cache.match_cache import MatchDataCache

@pytest.mark.unit
@pytest.mark.slash_commands
class TestAskCommand:
    """Test suite for ask slash command."""
    
    def test_extract_match_id_from_thread_name(self, test_config, mock_openai_client):
        """Test match ID extraction from various thread name formats."""
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        # Valid formats
        assert cog._extract_match_id("Match 8451070414 - 2025-01-01") == 8451070414
        assert cog._extract_match_id("Match 1234567890 Discussion") == 1234567890
        assert cog._extract_match_id("Herald Analysis: Match 9876543210") == 9876543210
        
        # Invalid formats
        assert cog._extract_match_id("Random thread name") is None
        assert cog._extract_match_id("Match without number") is None
        assert cog._extract_match_id("") is None
        assert cog._extract_match_id("12345 no match prefix") is None

    @pytest.mark.asyncio
    async def test_ask_command_not_in_thread(self, test_config, mock_openai_client):
        """Test ask command behavior when not in a thread."""
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        # Mock interaction not in thread
        mock_interaction = AsyncMock()
        mock_interaction.channel = MagicMock()  # Not a Thread
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()
        
        await cog.ask_about_match(mock_interaction, "test question")
        
        # Should defer and send error message
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
        
        call_args = mock_interaction.followup.send.call_args
        assert "only works in Herald match threads" in call_args[0][0]
        assert call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_ask_command_invalid_thread_name(self, test_config, mock_openai_client):
        """Test ask command with thread that doesn't contain match ID."""
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        # Mock interaction in thread with invalid name
        mock_interaction = AsyncMock()
        mock_thread = AsyncMock(spec=discord.Thread)
        mock_thread.name = "Random Discussion Thread"
        mock_interaction.channel = mock_thread
        
        await cog.ask_about_match(mock_interaction, "test question")
        
        # Should send match ID error
        call_args = mock_interaction.followup.send.call_args
        assert "Could not find match ID" in call_args[0][0]

    @pytest.mark.asyncio  
    @patch('src.commands.ask_command.get_match_details')
    @patch('src.commands.ask_command.get_match_analysis')
    async def test_ask_command_cache_hit(self, mock_stratz, mock_opendota, test_config, mock_openai_client, sample_herald_match, sample_stratz_data):
        """Test ask command using cached data."""
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        # Pre-populate cache
        await cache.set(8451070414, sample_herald_match, sample_stratz_data)
        
        # Mock interaction
        mock_interaction = AsyncMock()
        mock_thread = AsyncMock(spec=discord.Thread)
        mock_thread.name = "Match 8451070414 - 2025-01-01"
        mock_interaction.channel = mock_thread
        
        await cog.ask_about_match(mock_interaction, "Why did this match last so long?")
        
        # Should not call APIs (cache hit)
        mock_opendota.assert_not_called()
        mock_stratz.assert_not_called()
        
        # Should generate AI response
        mock_openai_client.chat.completions.create.assert_called_once()
        
        # Should send response
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.commands.ask_command.get_match_details')
    @patch('src.commands.ask_command.get_match_analysis')
    async def test_ask_command_api_error_handling(self, mock_stratz, mock_opendota, test_config, mock_openai_client):
        """Test ask command error handling when APIs fail.""" 
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        # Mock API failures
        mock_opendota.side_effect = ValueError("OpenDota API failed")
        
        # Mock interaction
        mock_interaction = AsyncMock()
        mock_thread = AsyncMock(spec=discord.Thread)
        mock_thread.name = "Match 8451070414 - 2025-01-01"
        mock_interaction.channel = mock_thread
        
        await cog.ask_about_match(mock_interaction, "test question")
        
        # Should send error message
        call_args = mock_interaction.followup.send.call_args
        assert "Failed to analyze match" in call_args[0][0]
        assert call_args[1]["ephemeral"] is True

@pytest.mark.unit  
@pytest.mark.cache
class TestMatchCache:
    """Test suite for match data caching."""
    
    @pytest.mark.asyncio
    async def test_cache_basic_operations(self):
        """Test basic cache set/get operations."""
        cache = MatchDataCache(ttl_hours=1)
        
        # Should return None for non-existent key
        result = await cache.get(12345)
        assert result is None
        
        # Set and retrieve data
        test_data = ("match_details", "stratz_data")
        await cache.set(12345, *test_data)
        
        cached_result = await cache.get(12345)
        assert cached_result == test_data
        
        # Verify stats
        stats = await cache.stats()
        assert stats["entries"] == 1
        assert stats["total_accesses"] == 1

    @pytest.mark.asyncio
    async def test_cache_capacity_management(self):
        """Test cache capacity limits and eviction."""
        cache = MatchDataCache(ttl_hours=1, max_entries=3)
        
        # Fill cache to capacity
        for i in range(3):
            await cache.set(i, f"match_{i}", f"stratz_{i}")
        
        stats = await cache.stats()
        assert stats["entries"] == 3
        
        # Adding another entry should evict oldest
        await cache.set(3, "match_3", "stratz_3")
        
        stats = await cache.stats()
        assert stats["entries"] == 3
        
        # Oldest entry should be gone
        result = await cache.get(0)
        assert result is None
        
        # Newest entry should exist
        result = await cache.get(3)
        assert result is not None
```

#### 2. Integration Tests with API Mocking
**File**: `tests/integration/test_ask_integration.py`
**Changes**: Integration tests with real API response validation

```python
"""Integration tests for ask command with API mocking."""
import pytest
import aioresponses
import json
from unittest.mock import AsyncMock, patch

from src.commands.ask_command import AskCommandCog
from src.cache.match_cache import MatchDataCache
from src.api.opendota import get_match_details
from src.api.stratz import get_match_analysis

@pytest.mark.integration
@pytest.mark.openai
class TestAskIntegration:
    """Integration tests for complete ask command flow."""
    
    @pytest.mark.asyncio
    async def test_complete_ask_flow_with_api_mocking(self, test_config, mock_openai_client, real_api_responses, aioresponses_mock):
        """Test complete ask command flow with mocked APIs."""
        
        # Mock OpenDota match details API
        aioresponses_mock.get(
            "https://api.opendota.com/api/matches/8451070414",
            payload=real_api_responses["opendota_match"]
        )
        
        # Mock Stratz GraphQL API
        aioresponses_mock.post(
            "https://api.stratz.com/graphql", 
            payload=real_api_responses["stratz_graphql"]
        )
        
        # Setup ask command
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        # Mock Discord interaction
        mock_interaction = AsyncMock()
        mock_thread = AsyncMock()
        mock_thread.name = "Match 8451070414 - 2025-01-01"
        mock_interaction.channel = mock_thread
        
        # Execute ask command
        await cog.ask_about_match(mock_interaction, "What caused the most deaths in this match?")
        
        # Verify API calls were made
        assert len(aioresponses_mock.requests) == 2
        
        # Verify OpenAI was called with match data
        mock_openai_client.chat.completions.create.assert_called_once()
        call_args = mock_openai_client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][0]["content"]
        
        # Verify prompt contains match data
        assert "8451070414" in prompt
        assert "Herald" in prompt
        assert "Duration:" in prompt
        assert "COMPLETE MATCH DATA:" in prompt
        
        # Verify response was sent
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_integration_reduces_api_calls(self, test_config, mock_openai_client, real_api_responses, aioresponses_mock):
        """Test that cache integration actually reduces API calls."""
        
        # Mock APIs (will only be called once due to caching)
        aioresponses_mock.get(
            "https://api.opendota.com/api/matches/8451070414",
            payload=real_api_responses["opendota_match"]
        )
        aioresponses_mock.post(
            "https://api.stratz.com/graphql",
            payload=real_api_responses["stratz_graphql"]
        )
        
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        # Mock Discord interaction
        mock_interaction = AsyncMock()
        mock_thread = AsyncMock()
        mock_thread.name = "Match 8451070414 - 2025-01-01"
        mock_interaction.channel = mock_thread
        
        # First call - should hit APIs
        await cog.ask_about_match(mock_interaction, "First question")
        assert len(aioresponses_mock.requests) == 2  # Both APIs called
        
        # Second call - should use cache
        mock_interaction.reset_mock()
        await cog.ask_about_match(mock_interaction, "Second question")
        assert len(aioresponses_mock.requests) == 2  # No additional API calls
        
        # Verify cache stats
        stats = await cache.stats()
        assert stats["entries"] == 1
        assert stats["total_accesses"] == 2  # Cache accessed twice

@pytest.mark.integration  
@pytest.mark.error_scenarios
class TestErrorScenarios:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_opendota_api_failure(self, test_config, mock_openai_client, aioresponses_mock):
        """Test handling of OpenDota API failures."""
        
        # Mock API failure
        aioresponses_mock.get(
            "https://api.opendota.com/api/matches/8451070414",
            status=500
        )
        
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        mock_interaction = AsyncMock()
        mock_thread = AsyncMock()
        mock_thread.name = "Match 8451070414 - 2025-01-01"
        mock_interaction.channel = mock_thread
        
        # Should handle error gracefully
        await cog.ask_about_match(mock_interaction, "test question")
        
        # Should send error message
        call_args = mock_interaction.followup.send.call_args
        assert "Failed to analyze match" in call_args[0][0]
        assert call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_openai_api_failure(self, test_config, real_api_responses, aioresponses_mock):
        """Test handling of OpenAI API failures."""
        
        # Mock successful data APIs
        aioresponses_mock.get(
            "https://api.opendota.com/api/matches/8451070414",
            payload=real_api_responses["opendota_match"]
        )
        aioresponses_mock.post(
            "https://api.stratz.com/graphql",
            payload=real_api_responses["stratz_graphql"]
        )
        
        # Mock failing OpenAI client
        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI API failed")
        
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        mock_interaction = AsyncMock()
        mock_thread = AsyncMock()
        mock_thread.name = "Match 8451070414 - 2025-01-01" 
        mock_interaction.channel = mock_thread
        
        await cog.ask_about_match(mock_interaction, "test question")
        
        # Should cache data even if OpenAI fails
        cached_data = await cache.get(8451070414)
        assert cached_data is not None
        
        # Should send error message
        call_args = mock_interaction.followup.send.call_args
        assert "Failed to analyze match" in call_args[0][0]
```

#### 3. End-to-End Discord Tests  
**File**: `tests/e2e/test_discord_slash_commands.py`
**Changes**: Real Discord bot testing with slash commands

```python
"""End-to-end tests for Discord slash command functionality."""
import pytest
import os
import asyncio
import discord
from unittest.mock import AsyncMock, patch

from src.bot import HeraldBot
from src.config import Config

@pytest.mark.e2e
@pytest.mark.discord
@pytest.mark.slash_commands
class TestDiscordSlashCommands:
    """End-to-end tests for slash command integration."""
    
    @pytest.mark.asyncio
    async def test_slash_command_registration(self, test_config, mock_openai_client):
        """Test that slash commands are properly registered with Discord."""
        
        with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
            bot = HeraldBot(test_config)
            
            # Mock Discord connection
            bot.user = AsyncMock()
            bot.user.id = 12345
            bot.guilds = []
            
            # Simulate setup hook
            await bot.setup_hook()
            
            # Verify ask command cog was added
            cog = bot.get_cog('AskCommandCog')
            assert cog is not None
            
            # Verify command exists
            ask_command = bot.tree.get_command('ask')
            assert ask_command is not None
            assert ask_command.description == "Ask questions about the Herald match in this thread"

@pytest.mark.e2e
@pytest.mark.live_api
@pytest.mark.skipif(
    not os.getenv("DISCORD_BOT_TOKEN") or not os.getenv("DISCORD_TEST_CHANNEL_ID"),
    reason="Live Discord credentials not available"
)
class TestLiveDiscordSlashCommands:
    """Tests that actually connect to Discord and test slash commands."""
    
    @pytest.mark.asyncio
    async def test_real_slash_command_interaction(self, real_api_responses):
        """Test actual slash command interaction with Discord."""
        
        # Create real bot with live credentials
        config = Config(
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
            discord_test_channel_id=int(os.getenv("DISCORD_TEST_CHANNEL_ID")),
            discord_test_thread_id=int(os.getenv("DISCORD_TEST_THREAD_ID", "0")),
            opendota_api_key="test_key",
            stratz_api_token="test_token", 
            openai_api_key="test_openai"
        )
        
        bot = HeraldBot(config)
        
        # Mock APIs to avoid real calls
        with patch('src.api.opendota.get_match_details') as mock_opendota, \
             patch('src.api.stratz.get_match_analysis') as mock_stratz, \
             patch('openai.AsyncOpenAI') as mock_openai_cls:
            
            # Setup API mocks
            mock_opendota.return_value = AsyncMock()
            mock_stratz.return_value = AsyncMock()
            
            mock_openai = AsyncMock()
            mock_response = AsyncMock()
            mock_choice = AsyncMock()
            mock_message = AsyncMock()
            mock_message.content = "Test AI response for e2e testing."
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_openai.chat.completions.create.return_value = mock_response
            mock_openai_cls.return_value = mock_openai
            
            async def test_interaction():
                await bot.wait_until_ready()
                
                # Get test channel and create test thread
                channel = bot.get_channel(config.discord_test_channel_id)
                assert channel is not None, "Test channel not accessible"
                
                # Create test thread with match ID pattern
                test_message = await channel.send("Test message for e2e slash command testing")
                test_thread = await test_message.create_thread(
                    name="Match 8451070414 - 2025-01-01 E2E Test"
                )
                
                try:
                    # Simulate slash command interaction 
                    # Note: In real testing, this would be triggered by Discord user
                    # For automation, we test the command logic directly
                    
                    ask_cog = bot.get_cog('AskCommandCog')
                    assert ask_cog is not None
                    
                    # Create mock interaction
                    mock_interaction = AsyncMock()
                    mock_interaction.channel = test_thread
                    mock_interaction.response.defer = AsyncMock()
                    mock_interaction.followup.send = AsyncMock()
                    
                    # Test the slash command
                    await ask_cog.ask_about_match(mock_interaction, "Why did this Herald match last so long?")
                    
                    # Verify interaction flow
                    mock_interaction.response.defer.assert_called_once()
                    mock_interaction.followup.send.assert_called_once()
                    
                    # Verify AI response was generated  
                    call_args = mock_interaction.followup.send.call_args
                    response_text = call_args[0][0]
                    assert "Test AI response" in response_text
                    
                finally:
                    # Cleanup test thread
                    await test_thread.delete()
                    await test_message.delete()
                    
                await bot.close()
            
            # Run live test
            task = asyncio.create_task(test_interaction())
            
            try:
                await bot.start(config.discord_bot_token)
            except Exception as e:
                if "already running" not in str(e).lower():
                    raise e
            finally:
                await task
```

#### 4. Performance and Cache Tests
**File**: `tests/performance/test_cache_performance.py`
**Changes**: Performance validation for caching system

```python
"""Performance tests for cache and API integration."""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch

from src.cache.match_cache import MatchDataCache
from src.commands.ask_command import AskCommandCog

@pytest.mark.performance
@pytest.mark.cache
class TestCachePerformance:
    """Performance tests for match data caching."""
    
    @pytest.mark.asyncio
    async def test_cache_access_performance(self):
        """Test cache access time under load."""
        cache = MatchDataCache()
        
        # Populate cache with test data
        for i in range(50):
            await cache.set(i, f"match_{i}", f"stratz_{i}")
        
        # Measure cache access time
        start_time = time.time()
        
        # Perform 100 cache accesses
        for _ in range(100):
            for i in range(0, 50, 5):  # Access every 5th entry
                result = await cache.get(i)
                assert result is not None
        
        end_time = time.time()
        access_time = end_time - start_time
        
        # Should complete 100 accesses in under 1 second
        assert access_time < 1.0, f"Cache access took {access_time:.2f}s, expected < 1.0s"
        
        # Verify cache stats
        stats = await cache.stats()
        assert stats["total_accesses"] == 1000  # 100 rounds * 10 entries each

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test cache performance under concurrent access."""
        cache = MatchDataCache()
        
        async def cache_worker(worker_id: int):
            """Worker function for concurrent cache operations."""
            for i in range(10):
                match_id = worker_id * 10 + i
                
                # Set data
                await cache.set(match_id, f"match_{match_id}", f"stratz_{match_id}")
                
                # Get data
                result = await cache.get(match_id)
                assert result is not None
                
                # Small delay to simulate real usage
                await asyncio.sleep(0.001)
        
        # Run 10 concurrent workers
        start_time = time.time()
        
        tasks = [cache_worker(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete concurrent operations quickly
        assert total_time < 2.0, f"Concurrent operations took {total_time:.2f}s, expected < 2.0s"
        
        # Verify all data was stored
        stats = await cache.stats()
        assert stats["entries"] == 100

    @pytest.mark.asyncio
    @patch('src.commands.ask_command.get_match_details')
    @patch('src.commands.ask_command.get_match_analysis')
    async def test_api_call_reduction_performance(self, mock_stratz, mock_opendota, test_config, mock_openai_client):
        """Test that caching provides significant performance improvement."""
        
        # Setup mocks with artificial delay
        async def slow_opendota(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate API delay
            return AsyncMock()
            
        async def slow_stratz(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate API delay  
            return AsyncMock()
            
        mock_opendota.side_effect = slow_opendota
        mock_stratz.side_effect = slow_stratz
        
        cache = MatchDataCache()
        cog = AskCommandCog(None, test_config, cache, mock_openai_client)
        
        # Mock Discord interaction
        mock_interaction = AsyncMock()
        mock_thread = AsyncMock()
        mock_thread.name = "Match 8451070414 - 2025-01-01"
        mock_interaction.channel = mock_thread
        
        # First call - should be slow (APIs called)
        start_time = time.time()
        await cog.ask_about_match(mock_interaction, "First question")
        first_call_time = time.time() - start_time
        
        # Reset mock for second call
        mock_interaction.reset_mock()
        
        # Second call - should be fast (cache hit)
        start_time = time.time()
        await cog.ask_about_match(mock_interaction, "Second question")  
        second_call_time = time.time() - start_time
        
        # Cache should provide significant speedup
        assert second_call_time < first_call_time * 0.5, f"Cache didn't improve performance: {second_call_time:.3f}s vs {first_call_time:.3f}s"
        
        # Verify API was only called once
        assert mock_opendota.call_count == 1
        assert mock_stratz.call_count == 1
```

### Success Criteria:

#### Automated Verification:
- [ ] All unit tests pass: `make test-unit`
- [ ] All integration tests pass: `make test-integration`
- [ ] All non-live e2e tests pass: `make test-e2e`
- [ ] Cache performance tests meet timing requirements: `make test-coverage | grep performance`
- [ ] Test coverage exceeds 90%: `make test-coverage`
- [ ] All test markers work correctly: `pytest --collect-only --strict-markers`

#### Manual Verification:
- [ ] Live Discord slash command tests work with real bot token: `make test-live`
- [ ] Ask command responds appropriately to different question types
- [ ] Cache statistics show expected hit ratios during repeated testing
- [ ] Error scenarios provide user-friendly messages
- [ ] Performance meets requirements under simulated load
- [ ] Test suite runs quickly for development feedback (< 30 seconds for unit tests)

---

## Phase 4: Integration and Performance Optimization

### Overview
Integrate ask command with existing periodic posting functionality, optimize performance, and add monitoring capabilities.

### Changes Required:

#### 1. Enhanced Bot Integration  
**File**: `src/bot.py`
**Changes**: Optimize bot for combined periodic + interactive usage

```python
"""Enhanced Herald Discord bot with optimized integration."""
import discord
from discord.ext import commands, tasks
import asyncio
import logging
import openai
from datetime import datetime, timedelta

from .config import Config
from .cache.match_cache import MatchDataCache
from .commands.ask_command import AskCommandCog
from .herald_reporter import run_herald_report

logger = logging.getLogger(__name__)

class HeraldBot(commands.Bot):
    """Production Herald Discord bot with caching and monitoring."""
    
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            # Add performance optimizations
            chunk_guilds_at_startup=False,
            member_cache_flags=discord.MemberCacheFlags.none()
        )
        
        self.config = config
        
        # Enhanced cache with monitoring
        self.match_cache = MatchDataCache(
            ttl_hours=4,  # Longer TTL for better hit rates
            max_entries=100  # Increased capacity
        )
        
        # Initialize OpenAI with retry config
        if config.openai_api_key:
            self.openai_client = openai.AsyncOpenAI(
                api_key=config.openai_api_key,
                timeout=30.0,
                max_retries=2
            )
        else:
            logger.warning("OpenAI API key not provided")
            self.openai_client = None
            
        # Performance monitoring
        self.stats = {
            'commands_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls_saved': 0,
            'errors_handled': 0,
            'uptime_start': datetime.utcnow()
        }
        
    async def setup_hook(self):
        """Enhanced setup with error handling."""
        logger.info("Bot is setting up...")
        
        try:
            # Add command cog
            if self.openai_client:
                await self.add_cog(AskCommandCog(self, self.config, self.match_cache, self.openai_client))
                logger.info("Ask command cog loaded successfully")
            else:
                logger.warning("Ask command not loaded - missing OpenAI API key")
            
            # Sync commands in development only
            if self.config.discord_test_channel_id:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")
                
        except Exception as e:
            logger.error(f"Setup hook failed: {e}")
            raise
    
    async def on_ready(self):
        """Enhanced ready event with monitoring."""
        logger.info(f"Bot connected as {self.user} to {len(self.guilds)} guilds")
        
        # Start monitoring task
        self.monitoring_task.start()
        
        # Start herald reporting with staggered start
        await asyncio.sleep(30)  # Wait 30s after startup
        self.herald_report_task.start()
        
    async def on_command_error(self, ctx, error):
        """Global command error handler."""
        self.stats['errors_handled'] += 1
        logger.error(f"Command error: {error}")
        
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
            
        await ctx.send(f"❌ An error occurred: {str(error)[:100]}", ephemeral=True)
    
    @tasks.loop(hours=24) 
    async def herald_report_task(self):
        """Enhanced periodic Herald reporting with cache integration."""
        try:
            logger.info("Starting Herald report task...")
            
            # Pass cache to reporter for potential reuse
            await run_herald_report(self, self.config, self.match_cache)
            
            logger.info("Herald report task completed successfully")
            
        except Exception as e:
            logger.error(f"Herald report task failed: {e}")
            self.stats['errors_handled'] += 1
    
    @tasks.loop(minutes=15)
    async def monitoring_task(self):
        """Periodic monitoring and cache maintenance."""
        try:
            # Log cache performance
            cache_stats = await self.match_cache.stats()
            self.stats['cache_hits'] = cache_stats.get('total_accesses', 0)
            
            logger.info(f"Cache stats: {cache_stats['entries']} entries, {cache_stats['total_accesses']} accesses")
            
            # Estimate API calls saved
            if cache_stats['total_accesses'] > cache_stats['entries']:
                self.stats['api_calls_saved'] = (cache_stats['total_accesses'] - cache_stats['entries']) * 2
            
        except Exception as e:
            logger.error(f"Monitoring task failed: {e}")
    
    @herald_report_task.before_loop
    async def before_herald_report(self):
        """Wait for bot ready."""
        await self.wait_until_ready()
        
    @monitoring_task.before_loop  
    async def before_monitoring(self):
        """Wait for bot ready."""
        await self.wait_until_ready()
    
    async def close(self):
        """Enhanced cleanup with statistics logging."""
        try:
            uptime = datetime.utcnow() - self.stats['uptime_start']
            logger.info(f"Bot shutting down after {uptime}")
            logger.info(f"Final stats: {self.stats}")
            
            # Cancel tasks
            self.herald_report_task.cancel()
            self.monitoring_task.cancel()
            
            # Close OpenAI client
            if hasattr(self.openai_client, 'close'):
                await self.openai_client.close()
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        finally:
            await super().close()
```

#### 2. Performance Optimized Herald Reporter
**File**: `src/herald_reporter.py`
**Changes**: Integrate caching with periodic reporting

```python
"""Enhanced Herald reporter with cache integration."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from .config import Config
from .api.opendota import discover_herald_matches, get_match_details
from .api.stratz import get_match_analysis, validate_herald_match
from .discord.embeds import create_match_embed, create_team_embed
from .discord.channels import get_verified_channels, create_match_thread, cleanup_old_threads
from .cache.match_cache import MatchDataCache

logger = logging.getLogger(__name__)

async def run_herald_report(bot, config: Config, cache: Optional[MatchDataCache] = None):
    """Enhanced Herald reporting pipeline with cache integration."""
    logger.info("Starting Herald match analysis...")
    
    try:
        # Get verified Discord channels
        channel_ids = [config.discord_test_channel_id]
        channels = await get_verified_channels(bot, channel_ids)
        
        if not channels:
            logger.error("No accessible Discord channels found")
            return
        
        # Clean up old threads first
        for channel in channels:
            await cleanup_old_threads(channel, config.thread_retention_days)
        
        # Discover Herald matches
        herald_matches = await discover_herald_matches(config)
        
        if not herald_matches:
            logger.info("No Herald matches found")
            return
        
        logger.info(f"Processing {len(herald_matches)} Herald matches...")
        
        # Process each match with cache optimization
        for match in herald_matches:
            try:
                await _process_single_match_with_cache(
                    match.match_id, channels, config, cache
                )
                
                # Delay between matches
                await asyncio.sleep(config.api_delay_seconds)
                
            except Exception as e:
                logger.error(f"Failed to process match {match.match_id}: {e}")
                continue
        
        logger.info("Herald report completed successfully")
        
    except Exception as e:
        logger.error(f"Herald report failed: {e}")
        raise

async def _process_single_match_with_cache(match_id: int, channels: List, config: Config, cache: Optional[MatchDataCache]):
    """Process a single match with cache integration."""
    logger.info(f"Processing match {match_id}")
    
    # Check cache first if available
    match_details = None
    stratz_data = None
    
    if cache:
        cached_data = await cache.get(match_id)
        if cached_data:
            match_details, stratz_data = cached_data
            logger.info(f"Using cached data for match {match_id} (periodic report)")
    
    # Fetch fresh data if not cached
    if not match_details or not stratz_data:
        # Get match details from OpenDota
        match_details = await get_match_details(config, match_id)
        
        if match_details.has_leavers:
            logger.info(f"Match {match_id} has leavers, skipping")
            return
        
        # Delay before Stratz call
        await asyncio.sleep(config.api_delay_seconds)
        
        # Get enhanced player data from Stratz
        stratz_data = await get_match_analysis(config, match_id)
        
        # Cache the results for future ask commands
        if cache:
            await cache.set(match_id, match_details, stratz_data)
            logger.info(f"Cached match data for {match_id} (periodic report)")
    
    # Validate Herald ranks
    if not validate_herald_match(stratz_data):
        return
    
    # Create Discord embeds
    match_embed = create_match_embed(match_details, stratz_data)
    radiant_embed = create_team_embed(stratz_data.radiant_players, True)
    dire_embed = create_team_embed(stratz_data.dire_players, False)
    
    # Post to all channels
    for channel in channels:
        try:
            # Create match thread
            match_date = datetime.fromtimestamp(match_details.start_time, tz=timezone.utc)
            thread = await create_match_thread(channel, match_embed, match_id, match_date)
            
            if thread:
                # Post team embeds to thread
                await thread.send(embed=radiant_embed)
                await asyncio.sleep(1)  # Rate limiting
                await thread.send(embed=dire_embed)
                
                logger.info(f"Successfully posted match {match_id} to channel {channel.name}")
            
        except Exception as e:
            logger.error(f"Failed to post match {match_id} to channel {channel.name}: {e}")
            continue
```

#### 3. Enhanced Configuration
**File**: `src/config.py`  
**Changes**: Add performance and monitoring configuration

```python
"""Enhanced configuration with performance settings."""
import os
from typing import List
from pydantic import BaseModel, Field, validator

class Config(BaseModel):
    """Enhanced application configuration."""
    
    # Discord
    discord_bot_token: str = Field(...)
    discord_test_channel_id: int = Field(...)
    discord_test_thread_id: int = Field(...)
    
    # APIs
    opendota_api_key: str = Field(...)
    stratz_api_token: str = Field(...)
    openai_api_key: str = Field(default="")
    
    # Bot behavior
    query_days_back: int = Field(default=2)
    thread_retention_days: int = Field(default=10)
    api_delay_seconds: int = Field(default=1)
    
    # Performance settings
    cache_ttl_hours: int = Field(default=4)
    cache_max_entries: int = Field(default=100)
    openai_timeout_seconds: int = Field(default=30)
    openai_max_retries: int = Field(default=2)
    
    # Monitoring
    enable_performance_logging: bool = Field(default=True)
    log_cache_stats_interval: int = Field(default=15)  # minutes
    
    @validator('discord_test_channel_id', 'discord_test_thread_id')
    def validate_discord_ids(cls, v):
        if v and v < 1000:  # Discord IDs are very large numbers
            raise ValueError('Discord IDs must be valid snowflake IDs')
        return v
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN", ""),
            discord_test_channel_id=int(os.getenv("DISCORD_TEST_CHANNEL_ID", "0")),
            discord_test_thread_id=int(os.getenv("DISCORD_TEST_THREAD_ID", "0")),
            opendota_api_key=os.getenv("OPENDOTA_API_KEY", ""),
            stratz_api_token=os.getenv("STRATZ_API_TOKEN", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            # Performance settings from environment
            cache_ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "4")),
            cache_max_entries=int(os.getenv("CACHE_MAX_ENTRIES", "100")),
            enable_performance_logging=os.getenv("ENABLE_PERFORMANCE_LOGGING", "true").lower() == "true",
        )
    
    def validate_required(self) -> None:
        """Validate required fields with enhanced error messages."""
        required_fields = {
            "discord_bot_token": "Discord bot token",
            "discord_test_channel_id": "Discord test channel ID", 
            "opendota_api_key": "OpenDota API key",
            "stratz_api_token": "Stratz API token"
        }
        
        missing = []
        for field, description in required_fields.items():
            if not getattr(self, field):
                missing.append(f"{description} ({field})")
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
```

### Success Criteria:

#### Automated Verification:
- [ ] Enhanced bot starts without errors: `uv run python src/main.py --test-startup`
- [ ] Cache integration works: Monitor logs for "Using cached data" messages
- [ ] Performance monitoring logs cache statistics every 15 minutes
- [ ] All existing functionality preserved: Both periodic reports and ask commands work
- [ ] Memory usage stays stable under extended operation
- [ ] Configuration validation catches invalid settings

#### Manual Verification:
- [ ] Ask commands have <2 second response time for cached matches
- [ ] Periodic reports automatically populate cache for future ask commands
- [ ] Cache hit rate >70% during repeated testing of same matches
- [ ] Bot handles Discord reconnections gracefully
- [ ] Performance logs show API call reduction statistics
- [ ] Error handling provides actionable information for debugging

---

## Testing Strategy

### Comprehensive Test Coverage

**Unit Tests (70% of test suite):**
- Pydantic model validation with real API response data
- Cache operations (set/get/cleanup/eviction)
- Match ID extraction from thread names
- OpenAI prompt generation and response parsing
- Discord embed creation and formatting
- Configuration validation and environment loading

**Integration Tests (20% of test suite):**
- Complete ask command flow with HTTP mocking
- Cache integration reducing API calls
- Error handling scenarios (API failures, malformed responses)
- Performance tests for cache hit rates and response times

**End-to-End Tests (10% of test suite):**
- Live Discord slash command registration and interaction
- Real bot posting to test channels with mock APIs
- Complete workflow from match discovery to ask command response
- Thread creation and management integration

### Test Execution Strategy

```bash
# Development workflow
make test-quick          # Unit tests only (< 30 seconds)
make test-unit          # All unit tests with coverage
make test-integration   # Integration tests with mocking
make test-cache         # Cache performance validation
make test-openai        # OpenAI integration tests
make test-slash         # Slash command tests

# CI/CD workflow
make test              # All non-live tests
make test-coverage     # Full coverage report (target: 90%+)

# Live testing (requires real credentials)
make test-live         # Real Discord integration tests
```

## Performance Considerations

### Cache Optimization
- **In-Memory Storage**: No database overhead for small scale (10 users)
- **TTL Management**: 4-hour cache TTL balances freshness with API call reduction
- **Capacity Management**: 100-entry limit with LRU eviction for memory control
- **Concurrent Access**: Async locks prevent race conditions

### API Rate Limiting  
- **Sequential Processing**: 1-second delays between all external API calls
- **Cache First**: Always check cache before making API calls  
- **Intelligent Caching**: Periodic reports populate cache for interactive commands
- **Error Handling**: Failed API calls don't prevent cached data usage

### Discord Rate Limiting
- **Built-in Handling**: Discord.py handles rate limits automatically
- **Staggered Operations**: Delays between thread creation and message posting
- **Batch Processing**: Group related operations to minimize API calls

## Migration Notes

### From Existing Implementation Plan
- **Builds Upon**: Extends existing 4-phase plan rather than replacing it
- **Reuses Architecture**: Pure functions, Pydantic models, sequential processing
- **Adds Interactivity**: Slash commands complement periodic reporting
- **Enhances Testing**: Comprehensive test suite builds on existing pytest configuration

### Environment Compatibility  
- **Same Variables**: Uses identical environment variable names as existing plan
- **Backward Compatible**: Existing configuration files work without modification
- **Incremental Migration**: Can implement phases independently

## References

- Original Research: `thoughts/shared/research/2025-09-11_10-00-00_herald-bot-design-gaps-and-improvements.md`
- Base Implementation Plan: `thoughts/shared/plans/herald-discord-bot-implementation.md`
- API Response Samples: `opendota_query_response.json`, `stratz_graphql_response.json`
- Deprecated Patterns: `deprecated/discord_bot.py`, `deprecated/functions.py`
- Testing Configuration: `pytest.ini`, `requirements-test.txt`
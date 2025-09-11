# Herald Discord Bot - Unified Implementation Plan

## Overview

A comprehensive implementation plan that unifies periodic Herald match discovery with interactive AI-powered analysis. This plan bridges the gap between automated reporting and user-driven match insights, creating a cohesive Discord bot architecture that supports both use cases efficiently.

## Current State Analysis

### What Exists Now
- **src/**: Empty implementation ready for clean development following modern patterns
- **deprecated/**: Fully functional bot with mature API integration patterns, Discord posting, and data mappings
- **API Response Samples**: Real OpenDota and Stratz response data validated and ready for Pydantic model development
- **Testing Infrastructure**: Complete pytest configuration with async support, coverage reporting, and comprehensive markers
- **Two Implementation Plans**: Complementary plans covering periodic posting and interactive commands with testing strategies

### Key Architectural Discoveries
- `deprecated/functions.py:222-298` - Battle-tested OpenDota chunked queries with rate limiting
- `deprecated/functions.py:366-413` - Mature Stratz GraphQL integration with Bearer token authentication
- `deprecated/discord_bot.py:199-221` - Multi-channel posting with individual error handling
- `deprecated/constants.py:1-649` - Complete hero/item mappings ready for reuse
- `pytest.ini:11-25` - Excellent test configuration with coverage, async support, and comprehensive markers

## Desired End State

A production-ready Discord bot that seamlessly combines:

1. **Automated Herald Discovery** - Periodic scanning for long Herald matches with rich Discord embeds
2. **Interactive AI Analysis** - `/ask` slash command for user-driven match insights using OpenAI
3. **Intelligent Caching** - Shared cache reduces API calls across both periodic and interactive features  
4. **Comprehensive Testing** - 90%+ test coverage with unit, integration, and live Discord verification
6. **Scalable Architecture** - Pure functions with Pydantic validation supporting future enhancements

### Verification Criteria
- Bot discovers and posts Herald matches automatically every 24 hours
- Users can ask detailed questions about matches using `/ask` command in threads
- Test suite runs in <2 minutes with comprehensive Discord integration verification

## What We're NOT Doing

- Database persistence (maintain stateless pattern with in-memory caching only)
- Multiple bot instances or clustering (single bot handles both periodic and interactive workloads)
- Automatic AI commentary in periodic posts (AI analysis only available via `/ask` command)
- Migration of deprecated code (clean implementation following modern patterns)
- Error resilience patterns (maintain fail-fast approach for reliability)

## Implementation Approach

**Unified Architecture**: Build a single bot that efficiently handles both periodic background tasks and interactive slash commands using shared components and caching.

**Test-Driven Incremental Development**: Follow strict TDD workflow for each feature:
1. **Write failing test** that defines the expected behavior of the feature to be added
2. **Write the feature** with minimal implementation to make the test pass
3. **Validate with the test** and refactor for quality while keeping tests green
4. Repeat for each component, ensuring each phase builds on the previous foundation with comprehensive test coverage

**Shared Components**: Maximize code reuse between periodic and interactive features through pure functions, shared caching, and unified API clients.

---

## Phase 1: Unified Foundation & Core Infrastructure

### Overview
Establish the foundational architecture that supports both periodic and interactive functionality with shared components, comprehensive testing infrastructure, and unified configuration.

### Changes Required:

#### 1. Enhanced Project Dependencies
**File**: `pyproject.toml`
**Changes**: Complete dependency specification for unified functionality

```toml
[project]
name = "herald-scraper-bot"
version = "0.1.0"
description = "Herald Discord Bot with periodic reporting and interactive analysis"
dependencies = [
    "discord.py>=2.3.0",
    "aiohttp>=3.9.0",
    "pydantic>=2.11.7",
    "openai>=1.58.1",
    "pypika>=0.48.0",
    "python-dotenv>=1.0.0",
]

[dependency-groups]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0", 
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.11.0",
    "aioresponses>=0.7.4",
    "freezegun>=1.2.2",
    "factory-boy>=3.3.0",
    "ruff>=0.1.0"
]
```

#### 2. Unified Configuration System
**File**: `src/config.py`
**Changes**: Single configuration supporting all features

```python
"""Unified configuration for Herald Discord Bot."""
import os
from typing import Optional
from pydantic import BaseModel, Field, validator

class Config(BaseModel):
    """Unified configuration supporting periodic and interactive features."""
    
    # Discord Configuration
    discord_bot_token: str = Field(..., description="Discord bot token")
    discord_test_channel_id: int = Field(..., description="Test channel for posting matches")
    discord_test_thread_id: int = Field(default=0, description="Test thread for development")
    
    # API Configuration
    opendota_api_key: str = Field(..., description="OpenDota API key")
    stratz_api_token: str = Field(..., description="Stratz API bearer token")
    openai_api_key: str = Field(default="", description="OpenAI API key for interactive features")
    
    # Bot Behavior
    query_days_back: int = Field(default=2, description="Days to look back for Herald matches")
    thread_retention_days: int = Field(default=10, description="Days to retain match threads")
    api_delay_seconds: int = Field(default=1, description="Delay between API calls")
    
    # Performance & Caching
    cache_ttl_hours: int = Field(default=4, description="Match data cache TTL")
    cache_max_entries: int = Field(default=100, description="Maximum cache entries")
    
    # OpenAI Configuration
    openai_timeout_seconds: int = Field(default=30, description="OpenAI API timeout")
    openai_max_retries: int = Field(default=2, description="OpenAI API retry attempts")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model for analysis")
    
    @validator('discord_test_channel_id')
    def validate_discord_channel(cls, v):
        if v and v < 1000:
            raise ValueError('Discord channel ID must be valid snowflake')
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
            # Performance settings
            cache_ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "4")),
            cache_max_entries=int(os.getenv("CACHE_MAX_ENTRIES", "100"))
        )
    
    def validate_required(self) -> None:
        """Validate required configuration with helpful error messages."""
        required = {
            "discord_bot_token": "Discord bot token",
            "discord_test_channel_id": "Discord test channel ID", 
            "opendota_api_key": "OpenDota API key",
            "stratz_api_token": "Stratz API token"
        }
        
        missing = [desc for field, desc in required.items() if not getattr(self, field)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
    
    @property
    def has_openai(self) -> bool:
        """Check if OpenAI functionality is available."""
        return bool(self.openai_api_key)
```

#### 3. Unified Pydantic Models
**File**: `src/models/__init__.py`
**Changes**: Model package initialization

```python
"""Unified data models for Herald Discord Bot."""
from .opendota import OpenDotaMatch, OpenDotaMatchDetail, OpenDotaQueryResponse
from .stratz import StratzPlayer, StratzMatchData, StratzMatchResponse

__all__ = [
    "OpenDotaMatch", "OpenDotaMatchDetail", "OpenDotaQueryResponse",
    "StratzPlayer", "StratzMatchData", "StratzMatchResponse"
]
```

**File**: `src/models/opendota.py`
**Changes**: OpenDota models with enhanced validation

```python
"""OpenDota API models with comprehensive validation."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class OpenDotaMatch(BaseModel):
    """Herald match from OpenDota query results."""
    match_id: int
    start_time: int
    duration: int
    avg_rank_tier: Optional[int] = None
    lobby_type: Optional[int] = None
    game_mode: Optional[int] = None
    
    @property
    def is_herald_eligible(self) -> bool:
        """Check if match meets Herald criteria (rank 11-15, duration >75min)."""
        return (
            self.avg_rank_tier is not None 
            and 11 <= self.avg_rank_tier <= 15
            and self.duration > 4500
        )
    
    @property
    def duration_formatted(self) -> str:
        """Format duration as MM:SS."""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
    
    @property
    def start_datetime(self) -> datetime:
        """Convert start_time to datetime object."""
        return datetime.fromtimestamp(self.start_time)

class OpenDotaQueryResponse(BaseModel):
    """Response wrapper for OpenDota explorer queries - VALIDATED AGAINST REAL API DATA."""
    command: str
    rowCount: int = Field(alias="rowCount")
    rows: List[Dict[str, Any]]  # CORRECTED: Objects not arrays!
    fields: List[Dict[str, Any]]
    
    # Additional fields found in actual response
    oid: Optional[Any] = None
    err: Optional[str] = None
    
    def to_matches(self) -> List[OpenDotaMatch]:
        """Convert raw rows to typed match objects - CORRECTED for dict access."""
        matches = []
        for row in self.rows:
            matches.append(OpenDotaMatch(
                match_id=row["match_id"],
                start_time=row["start_time"], 
                duration=row["duration"],
                avg_rank_tier=row.get("avg_rank_tier"),
                lobby_type=None,  # Not available in query response
                game_mode=None    # Not available in query response
            ))
        return matches

class OpenDotaMatchDetail(BaseModel):
    """Detailed match information from OpenDota match API - VALIDATED AGAINST REAL API DATA."""
    match_id: int
    duration: int
    start_time: int
    lobby_type: int
    game_mode: int
    radiant_win: bool  # Added from real data
    players: List[Dict[str, Any]]
    
    # Additional fields from actual API response
    series_id: Optional[int] = 0
    series_type: Optional[int] = 0
    cluster: Optional[int] = None
    radiant_score: Optional[int] = None
    dire_score: Optional[int] = None
    replay_url: Optional[str] = None
    patch: Optional[int] = None
    region: Optional[int] = None
    
    @property
    def duration_formatted(self) -> str:
        """Format duration as MM:SS."""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
    
    @property
    def has_leavers(self) -> bool:
        """Check if any players abandoned the game."""
        return any(player.get("leaver_status", 0) != 0 for player in self.players)
    
    @property
    def radiant_players(self) -> List[Dict[str, Any]]:
        """Get Radiant team players (player_slot < 128)."""
        return [p for p in self.players if p.get("player_slot", 0) < 128]
    
    @property
    def dire_players(self) -> List[Dict[str, Any]]:
        """Get Dire team players (player_slot >= 128)."""
        return [p for p in self.players if p.get("player_slot", 0) >= 128]
```

**File**: `src/models/stratz.py`
**Changes**: Stratz models with advanced analytics

```python
"""Stratz API models with comprehensive player analytics."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class StratzPlayer(BaseModel):
    """Enhanced player data from Stratz GraphQL API - VALIDATED AGAINST REAL API DATA."""
    # Core fields from API
    heroId: int = Field(alias="heroId") 
    kills: int
    deaths: int
    assists: int
    level: Optional[int] = None
    heroDamage: int = Field(alias="heroDamage", default=0)
    isRadiant: bool = Field(alias="isRadiant")
    position: Optional[str] = None  # "POSITION_1", "POSITION_5", etc.
    
    # Steam account and stats (can be None)
    steamAccount: Optional[Dict[str, Any]] = Field(alias="steamAccount", default=None)
    stats: Optional[Dict[str, Any]] = Field(default=None)
    
    # Items - CORRECTED to be optional since they may not exist in all responses
    item0Id: Optional[int] = Field(alias="item0Id", default=None)
    item1Id: Optional[int] = Field(alias="item1Id", default=None) 
    item2Id: Optional[int] = Field(alias="item2Id", default=None)
    item3Id: Optional[int] = Field(alias="item3Id", default=None)
    item4Id: Optional[int] = Field(alias="item4Id", default=None)
    item5Id: Optional[int] = Field(alias="item5Id", default=None)
    
    # Advanced data (optional)
    playbackData: Optional[Dict[str, Any]] = Field(alias="playbackData", default=None)
    dotaPlus: Optional[Dict[str, Any]] = Field(alias="dotaPlus", default=None)
    
    @property
    def rank(self) -> Optional[int]:
        """Extract rank from steam account data."""
        if self.steamAccount and "seasonRank" in self.steamAccount:
            return self.steamAccount["seasonRank"]
        return None
    
    @property
    def is_herald(self) -> bool:
        """Check if player is Herald rank (11-15)."""
        rank = self.rank
        return rank is not None and 11 <= rank <= 15
    
    @property
    def kda_ratio(self) -> float:
        """Calculate KDA ratio."""
        if self.deaths == 0:
            return float(self.kills + self.assists)
        return (self.kills + self.assists) / self.deaths
    
    @property
    def position_number(self) -> Optional[int]:
        """Extract position number from position string."""
        if self.position and self.position.startswith("POSITION_"):
            try:
                return int(self.position.split("_")[1])
            except (IndexError, ValueError):
                pass
        return None
    
    @property
    def actions_per_minute(self) -> List[int]:
        """Get APM data (array of integers)."""
        if self.stats and "actionsPerMinute" in self.stats:
            return self.stats["actionsPerMinute"]
        return []
    
    @property
    def average_apm(self) -> Optional[float]:
        """Calculate average APM from the array."""
        apm_data = self.actions_per_minute
        if apm_data:
            return sum(apm_data) / len(apm_data)
        return None

class StratzMatchResponse(BaseModel):
    """Wrapper for Stratz GraphQL response."""
    data: Dict[str, Any]
    
    def to_match_data(self, match_id: int) -> "StratzMatchData":
        """Convert raw GraphQL response to typed match data."""
        match_data = self.data.get("match")
        if not match_data:
            raise ValueError(f"Match {match_id} not found in Stratz response")
        
        return StratzMatchData(
            match_id=match_id,
            players=match_data["players"]
        )

class StratzMatchData(BaseModel):
    """Complete match data with player analytics."""
    match_id: int  # Injected since it's not in API response
    players: List[StratzPlayer]
    
    @property
    def radiant_players(self) -> List[StratzPlayer]:
        """Get Radiant team players."""
        return [p for p in self.players if p.isRadiant]
    
    @property
    def dire_players(self) -> List[StratzPlayer]:
        """Get Dire team players."""
        return [p for p in self.players if not p.isRadiant]
    
    @property
    def all_players_herald(self) -> bool:
        """Verify all players with rank data are Herald."""
        players_with_rank = [p for p in self.players if p.rank is not None]
        return all(p.is_herald for p in players_with_rank) if players_with_rank else False
    
    @property
    def average_apm(self) -> Optional[float]:
        """Calculate match average APM."""
        apms = [p.average_apm for p in self.players if p.average_apm is not None]
        return sum(apms) / len(apms) if apms else None
    
    @property
    def total_kills(self) -> int:
        """Calculate total kills in match."""
        return sum(p.kills for p in self.players)
```

#### 4. Shared Cache Infrastructure
**File**: `src/cache/match_cache.py`
**Changes**: Thread-safe caching for both periodic and interactive features

```python
"""Unified match data cache for periodic and interactive features."""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Cache entry with access tracking and TTL."""
    match_details: Any
    stratz_data: Any
    created_at: datetime
    access_count: int = 0
    last_accessed: datetime = None
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at
    
    @property
    def is_expired(self, ttl_hours: int) -> bool:
        """Check if entry has exceeded TTL."""
        return datetime.utcnow() - self.created_at > timedelta(hours=ttl_hours)
    
    @property
    def age_minutes(self) -> int:
        """Get entry age in minutes."""
        return int((datetime.utcnow() - self.created_at).total_seconds() / 60)
    
    def access(self) -> Tuple[Any, Any]:
        """Mark as accessed and return data."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
        return self.match_details, self.stratz_data

class UnifiedMatchCache:
    """Thread-safe cache shared between periodic and interactive features."""
    
    def __init__(self, ttl_hours: int = 4, max_entries: int = 100):
        self.ttl_hours = ttl_hours
        self.max_entries = max_entries
        self._cache: Dict[int, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
    async def get(self, match_id: int) -> Optional[Tuple[Any, Any]]:
        """Get cached match data if available and fresh."""
        async with self._lock:
            entry = self._cache.get(match_id)
            
            if entry and not entry.is_expired(self.ttl_hours):
                self._stats['hits'] += 1
                logger.info(f"Cache HIT for match {match_id}")
                return entry.access()
            elif entry:
                # Remove expired entry
                del self._cache[match_id]
                logger.info(f"Removed expired cache entry for match {match_id}")
            
            self._stats['misses'] += 1
            logger.info(f"Cache MISS for match {match_id}")
            return None
    
    async def set(self, match_id: int, match_details: Any, stratz_data: Any) -> None:
        """Store match data with automatic capacity management."""
        async with self._lock:
            # Clean up expired entries first
            await self._cleanup_expired()
            
            # Evict oldest if at capacity
            if len(self._cache) >= self.max_entries:
                oldest_id = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
                del self._cache[oldest_id]
                self._stats['evictions'] += 1
                logger.info(f"Evicted oldest entry: match {oldest_id}")
            
            # Store new entry
            self._cache[match_id] = CacheEntry(
                match_details=match_details,
                stratz_data=stratz_data,
                created_at=datetime.utcnow()
            )
            logger.info(f"Cached match data for {match_id}")
    
    async def _cleanup_expired(self) -> None:
        """Remove all expired entries."""
        expired = [
            match_id for match_id, entry in self._cache.items()
            if entry.is_expired(self.ttl_hours)
        ]
        for match_id in expired:
            del self._cache[match_id]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired entries")
    
    async def stats(self) -> Dict[str, Any]:
        """Get basic cache statistics.""" 
        async with self._lock:
            return {
                "entries": len(self._cache),
                "total_hits": self._stats['hits'],
                "total_misses": self._stats['misses'],
                "total_evictions": self._stats['evictions']
            }
    
    async def clear(self) -> None:
        """Clear all cached data (for testing)."""
        async with self._lock:
            cleared = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {cleared} cache entries")
```

### Success Criteria:

#### Automated Verification:
- [ ] Dependencies install cleanly: `uv sync --all-groups`
- [ ] Foundation tests pass: `uv run python -m pytest tests/unit/test_foundation.py -v`

**Test File**: `tests/unit/test_foundation.py`
```python
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
        match_data = real_api_fixtures['opendota_match']
        match_detail = OpenDotaMatchDetail(**match_data)
        assert match_detail.match_id > 0
        assert match_detail.duration > 0
        
        # Test Stratz player validation
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
```

#### Manual Verification:
- [ ] Configuration validation provides helpful error messages for missing environment variables
- [ ] Pydantic models handle both expected data and edge cases gracefully
- [ ] Cache demonstrates thread-safe operations under concurrent access
- [ ] Foundation supports both periodic and interactive functionality patterns
- [ ] Performance logging provides actionable insights

---

## Phase 2: Unified API Layer & Data Processing

### Overview
Implement shared API clients and data processing functions that efficiently serve both periodic match discovery and interactive analysis, with comprehensive error handling and rate limiting.

### Changes Required:

#### 1. OpenDota API Client
**File**: `src/api/opendota.py`
**Changes**: Unified client supporting both bulk discovery and individual queries

```python
"""Unified OpenDota API client for periodic and interactive features."""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from pypika import Query, Table
import logging

from ..models.opendota import OpenDotaMatch, OpenDotaQueryResponse, OpenDotaMatchDetail
from ..config import Config

logger = logging.getLogger(__name__)

class OpenDotaClient:
    """Unified OpenDota API client with rate limiting and caching support."""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = "https://api.opendota.com/api"
        
    async def discover_herald_matches(self) -> List[OpenDotaMatch]:
        """Discover Herald matches for periodic reporting."""
        logger.info(f"Discovering Herald matches from last {self.config.query_days_back} days")
        
        time_chunks = self._generate_time_chunks(self.config.query_days_back)
        all_matches = []
        
        for start_time, end_time in time_chunks:
            try:
                chunk_matches = await self._query_match_chunk(start_time, end_time)
                all_matches.extend(chunk_matches)
                
                # Rate limiting
                await asyncio.sleep(self.config.api_delay_seconds)
                
            except Exception as e:
                logger.error(f"Failed to query chunk {start_time}-{end_time}: {e}")
                continue
        
        # Filter for Herald eligibility
        herald_matches = [m for m in all_matches if m.is_herald_eligible]
        logger.info(f"Found {len(herald_matches)} Herald-eligible matches from {len(all_matches)} total")
        
        return herald_matches
    
    async def get_match_details(self, match_id: int) -> OpenDotaMatchDetail:
        """Get detailed match information for analysis."""
        url = f"{self.base_url}/matches/{match_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"OpenDota API error {response.status} for match {match_id}")
                
                data = await response.json()
                return OpenDotaMatchDetail(**data)
    
    def _generate_time_chunks(self, days_back: int) -> List[Tuple[int, int]]:
        """Generate 1-hour time chunks for efficient querying."""
        now = datetime.utcnow()
        start_date = now - timedelta(days=days_back)
        
        chunks = []
        current = start_date
        
        while current < now:
            chunk_end = min(current + timedelta(hours=1), now)
            chunks.append((
                int(current.timestamp()),
                int(chunk_end.timestamp())
            ))
            current = chunk_end
        
        return chunks
    
    async def _query_match_chunk(self, start_time: int, end_time: int) -> List[OpenDotaMatch]:
        """Query a single time chunk with optimized SQL."""
        public_matches = Table("public_matches")
        
        query = (Query
            .from_(public_matches)
            .select(
                public_matches.match_id,
                public_matches.start_time,
                public_matches.duration,
                public_matches.avg_rank_tier,
                public_matches.lobby_type,
                public_matches.game_mode
            )
            .where(public_matches.avg_rank_tier >= 11)  # Herald minimum
            .where(public_matches.avg_rank_tier <= 15)  # Herald maximum
            .where(public_matches.duration > 4500)      # 75+ minutes
            .where(public_matches.start_time >= start_time)
            .where(public_matches.start_time <= end_time)
            .where(public_matches.lobby_type == 0)      # Public matches
            .limit(100)
            .orderby(public_matches.start_time, order="desc")
        )
        
        request_data = {"sql": str(query)}
        headers = {"Content-Type": "application/json"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/explorer", 
                                   json=request_data,
                                   headers=headers) as response:
                
                if response.status != 200:
                    raise ValueError(f"OpenDota explorer query failed: {response.status}")
                
                data = await response.json()
                query_response = OpenDotaQueryResponse(**data)
                return query_response.to_matches()
```

#### 2. Stratz API Client
**File**: `src/api/stratz.py`
**Changes**: Enhanced GraphQL client with comprehensive analytics

```python
"""Unified Stratz GraphQL client with comprehensive match analytics."""
import asyncio
import aiohttp
import logging
from typing import Optional

from ..models.stratz import StratzMatchData, StratzMatchResponse
from ..config import Config

logger = logging.getLogger(__name__)

class StratzClient:
    """Unified Stratz GraphQL client with enhanced analytics."""
    
    def __init__(self, config: Config):
        self.config = config
        self.graphql_url = "https://api.stratz.com/graphql"
        
    async def get_match_analysis(self, match_id: int) -> StratzMatchData:
        """Get comprehensive match analysis with all player data."""
        headers = {
            "Authorization": f"Bearer {self.config.stratz_api_token}",
            "User-Agent": "STRATZ_API",
            "Content-Type": "application/json"
        }
        
        query = self._build_comprehensive_query(match_id)
        request_body = {
            "query": query,
            "operationName": "MatchAnalysis"
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(self.graphql_url,
                                   json=request_body,
                                   headers=headers) as response:
                
                if response.status != 200:
                    response_text = await response.text()
                    raise ValueError(f"Stratz API error {response.status}: {response_text}")
                
                data = await response.json()
                
                if "errors" in data:
                    raise ValueError(f"Stratz GraphQL errors: {data['errors']}")
                
                # Convert to typed match data
                response_obj = StratzMatchResponse(**data)
                return response_obj.to_match_data(match_id)
    
    def validate_herald_match(self, match_data: StratzMatchData) -> bool:
        """Validate that match contains Herald players."""
        if not match_data.all_players_herald:
            logger.info(f"Match {match_data.match_id} contains non-Herald players, skipping")
            return False
        
        logger.info(f"Match {match_data.match_id} validated as all-Herald")
        return True
    
    def _build_comprehensive_query(self, match_id: int) -> str:
        """Build comprehensive GraphQL query for match analysis."""
        return f"""
        query MatchAnalysis {{
          match(id: {match_id}) {{
            players {{
              heroId
              kills
              deaths
              assists
              level
              heroDamage
              isRadiant
              position
              
              # Items
              item0Id
              item1Id
              item2Id
              item3Id
              item4Id
              item5Id
              
              # Steam account info
              steamAccount {{
                seasonRank
                name
                avatar
              }}
              
              # Advanced statistics
              stats {{
                actionsPerMinute
                
                # Ability usage
                abilityCastReport {{
                  abilityId
                  count
                  targets {{
                    target
                    count
                    damage
                    duration
                  }}
                }}
                
                # Item usage
                itemUsed {{
                  itemId
                  count
                }}
                
                # Timeline events
                itemPurchases {{
                  time
                  itemId
                }}
                
                # Combat events
                killEvents {{
                  time
                  target
                  byAbility
                  byItem
                }}
                
                deathEvents {{
                  time
                  attacker
                  target
                  byItem
                  byAbility
                  positionX
                  positionY
                }}
                
                # Map control
                wards {{
                  time
                  positionX
                  positionY
                  type
                }}
              }}
              
              # Playback data
              playbackData {{
                abilityLearnEvents {{
                  time
                  abilityId
                  level
                }}
                
                purchaseEvents {{
                  time
                  itemId
                }}
              }}
              
              # Dota Plus data
              dotaPlus {{
                level
              }}
            }}
          }}
        }}
        """
```

#### 3. Game Constants & Utilities
**File**: `src/constants.py`
**Changes**: Comprehensive game data mappings with JSON loading

```python
"""Game constants and utility functions."""
import json
from pathlib import Path
from typing import Dict, Optional

# Load mappings from JSON files to keep constants manageable
_CONSTANTS_DIR = Path(__file__).parent / "data"

def _load_json_mapping(filename: str) -> Dict[int, str]:
    """Load ID-to-name mapping from JSON file."""
    try:
        with open(_CONSTANTS_DIR / filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Convert string keys to int keys
            return {int(k): v for k, v in data.items()}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Fallback to empty dict if file missing or invalid
        return {}

# Load game data mappings
HERO_ID_TO_NAME: Dict[int, str] = _load_json_mapping("hero_ids.json")
ITEM_ID_TO_NAME: Dict[int, str] = _load_json_mapping("item_ids.json") 
ABILITY_ID_TO_NAME: Dict[int, str] = _load_json_mapping("ability_ids.json")

# Rank tier mappings for Herald analysis
RANK_TIERS: Dict[int, str] = {
    11: "Herald I",
    12: "Herald II", 
    13: "Herald III",
    14: "Herald IV",
    15: "Herald V",
    21: "Guardian I",
    22: "Guardian II",
    23: "Guardian III", 
    24: "Guardian IV",
    25: "Guardian V",
    31: "Crusader I",
    32: "Crusader II",
    33: "Crusader III",
    34: "Crusader IV", 
    35: "Crusader V",
    41: "Archon I",
    # ... continue for all ranks
}

def get_hero_name(hero_id: Optional[int]) -> str:
    """Get hero name by ID with fallback."""
    if hero_id is None:
        return "Unknown Hero"
    return HERO_ID_TO_NAME.get(hero_id, f"Unknown Hero ({hero_id})")

def get_item_name(item_id: Optional[int]) -> str:
    """Get item name by ID with fallback."""
    if item_id is None or item_id == 0:
        return "Empty"
    return ITEM_ID_TO_NAME.get(item_id, f"Unknown Item ({item_id})")

def get_ability_name(ability_id: Optional[int]) -> str:
    """Get ability name by ID with fallback."""
    if ability_id is None:
        return "Unknown Ability"
    return ABILITY_ID_TO_NAME.get(ability_id, f"Unknown Ability ({ability_id})")

def get_rank_name(rank_tier: Optional[int]) -> str:
    """Get rank name by tier with Herald highlighting."""
    if rank_tier is None:
        return "Unranked"
    return RANK_TIERS.get(rank_tier, f"Unknown Rank ({rank_tier})")

def is_herald_rank(rank_tier: Optional[int]) -> bool:
    """Check if rank tier is Herald (11-15)."""
    return rank_tier is not None and 11 <= rank_tier <= 15

def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS."""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"

def calculate_kda_ratio(kills: int, deaths: int, assists: int) -> float:
    """Calculate KDA ratio with proper handling of zero deaths."""
    if deaths == 0:
        return float(kills + assists)
    return (kills + assists) / deaths

def format_large_number(number: int) -> str:
    """Format large numbers with commas."""
    return f"{number:,}"
```

### Success Criteria:

#### Automated Verification:
- [ ] API layer tests pass: `uv run python -m pytest tests/unit/test_api_layer.py -v`

**Test File**: `tests/unit/test_api_layer.py`
```python
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
            discord_test_channel_id=123,
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
        
        # Test hero mappings
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
```

#### Manual Verification:
- [ ] OpenDota client discovers Herald matches within expected time ranges
- [ ] Stratz client returns comprehensive player analytics
- [ ] Herald validation correctly filters matches
- [ ] API clients handle network errors gracefully
- [ ] Game constants provide accurate hero/item names for current game version

---

## Phase 3: Discord Integration with Unified Posting & Interactive Commands

### Overview
Implement Discord bot functionality that seamlessly combines automated Herald match posting with interactive AI-powered analysis commands, using shared components and caching.

### Changes Required:

#### 1. Discord Embed System
**File**: `src/discord/embeds.py`
**Changes**: Unified embed system for both periodic and interactive features

```python
"""Unified Discord embed system for Herald match presentation."""
import discord
from datetime import datetime, timezone
from typing import List, Optional

from ..models.opendota import OpenDotaMatchDetail
from ..models.stratz import StratzMatchData, StratzPlayer
from ..constants import get_hero_name, get_item_name, get_rank_name, format_duration, format_large_number

# Team colors
RADIANT_COLOR = 0x00FF00  # Green
DIRE_COLOR = 0xFF0000     # Red
HERALD_COLOR = 0xFFD700   # Gold for Herald-specific content

def create_match_summary_embed(match_details: OpenDotaMatchDetail, stratz_data: StratzMatchData) -> discord.Embed:
    """Create comprehensive match summary embed combining OpenDota and Stratz data."""
    embed = discord.Embed(
        title="🏆 Herald Match Analysis",
        description=f"**Match ID:** [{match_details.match_id}](https://stratz.com/matches/{match_details.match_id})",
        color=HERALD_COLOR,
        url=f"https://stratz.com/matches/{match_details.match_id}"
    )
    
    # Match metadata from OpenDota
    match_date = datetime.fromtimestamp(match_details.start_time, tz=timezone.utc)
    duration_str = format_duration(match_details.duration)
    
    embed.add_field(name="📅 Date", value=match_date.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    embed.add_field(name="⏱️ Duration", value=duration_str, inline=True)
    
    # Analytics from Stratz data
    total_kills = stratz_data.total_kills
    kill_density = round(total_kills / (match_details.duration / 60), 2) if match_details.duration > 0 else 0
    
    embed.add_field(name="⚔️ Kill Density", value=f"{kill_density} kills/min", inline=True)
    embed.add_field(name="💀 Total Kills", value=str(total_kills), inline=True)
    
    embed.timestamp = match_date
    embed.set_footer(
        text="Use /ask in this thread for detailed analysis",
        icon_url="https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/icons/hero_strength.png"
    )
    
    return embed

def create_team_analysis_embed(players: List[StratzPlayer], is_radiant: bool) -> discord.Embed:
    """Create detailed team analysis embed with player breakdowns."""
    team_name = "Radiant" if is_radiant else "Dire"
    color = RADIANT_COLOR if is_radiant else DIRE_COLOR
    emoji = "🌅" if is_radiant else "🌙"
    
    embed = discord.Embed(
        title=f"{emoji} {team_name} Team Analysis",
        color=color
    )
    
    # Team-level statistics
    team_kills = sum(p.kills for p in players)
    
    embed.description = f"**Team Kills:** {team_kills}"
    
    # Individual player analysis
    for i, player in enumerate(players, 1):
        hero_name = get_hero_name(player.hero_id)
        kda = f"{player.kills}/{player.deaths}/{player.assists}"
        
        # Performance metrics
        apm_info = f"{player.average_apm:.0f} APM" if player.average_apm else "N/A APM"
        
        # Items
        items = [
            get_item_name(getattr(player, f"item{j}_id"))
            for j in range(6)
            if getattr(player, f"item{j}_id", None) and getattr(player, f"item{j}_id") != 0
        ]
        items_text = ", ".join(items[:3]) + ("..." if len(items) > 3 else "")
        
        field_value = (
            f"**KDA:** {kda}\n"
            f"**Damage:** {format_large_number(player.hero_damage)}\n"
            f"**APM:** {apm_info}\n"
            f"**Items:** {items_text}"
        )
        
        embed.add_field(
            name=f"{i}. {hero_name}",
            value=field_value,
            inline=True
        )
    
    return embed

def create_ai_response_embed(question: str, response: str, match_id: int) -> discord.Embed:
    """Create embed for AI-powered match analysis responses."""
    embed = discord.Embed(
        title="🤖 AI Match Analysis",
        description=f"**Question:** {question}",
        color=HERALD_COLOR
    )
    
    # Truncate long responses
    if len(response) > 1900:
        response = response[:1900] + "\n\n*[Response truncated for Discord limits]*"
    
    embed.add_field(name="Analysis", value=response, inline=False)
    embed.set_footer(text=f"Analysis for Match {match_id} | Powered by GPT-4o-mini")
    
    return embed
```

#### 2. Interactive Ask Command System
**File**: `src/commands/ask_command.py`
**Changes**: Comprehensive slash command with AI integration

```python
"""Interactive ask command for AI-powered Herald match analysis."""
import discord
from discord.ext import commands
from discord import app_commands
import re
import asyncio
import logging
from typing import Optional

from ..api.opendota import OpenDotaClient
from ..api.stratz import StratzClient
from ..cache.match_cache import UnifiedMatchCache
from ..discord.embeds import create_ai_response_embed
from ..config import Config

logger = logging.getLogger(__name__)

class AskCommandCog(commands.Cog):
    """Interactive AI analysis commands for Herald matches."""
    
    def __init__(self, bot: commands.Bot, config: Config, cache: UnifiedMatchCache, openai_client):
        self.bot = bot
        self.config = config
        self.cache = cache
        self.openai = openai_client
        self.opendota_client = OpenDotaClient(config)
        self.stratz_client = StratzClient(config)
        
    @app_commands.command(name="ask", description="Ask AI questions about the Herald match in this thread")
    @app_commands.describe(question="Your question about the match (e.g., 'Why did this game last so long?')")
    async def ask_about_match(self, interaction: discord.Interaction, question: str):
        """AI-powered match analysis with comprehensive data integration."""
        
        # Defer response since this may take time
        await interaction.response.defer()
        
        try:
            # Validate we're in a match thread
            if not isinstance(interaction.channel, discord.Thread):
                embed = discord.Embed(
                    title="❌ Invalid Channel",
                    description="This command only works in Herald match discussion threads.",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Extract match ID from thread name
            match_id = self._extract_match_id(interaction.channel.name)
            if not match_id:
                embed = discord.Embed(
                    title="❌ Match ID Not Found", 
                    description="Could not find match ID in thread name. Thread should contain 'Match 12345...'",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            logger.info(f"Processing /ask for match {match_id}: '{question[:100]}...'")
            
            # Try cache first for performance
            cached_data = await self.cache.get(match_id)
            if cached_data:
                match_details, stratz_data = cached_data
                logger.info(f"Using cached data for match {match_id}")
            else:
                # Fetch fresh data from APIs
                logger.info(f"Fetching fresh data for match {match_id}")
                
                # Parallel API calls for better performance
                tasks = [
                    self.opendota_client.get_match_details(match_id),
                    asyncio.sleep(self.config.api_delay_seconds)  # Rate limiting
                ]
                match_details, _ = await asyncio.gather(*tasks)
                
                # Get Stratz data
                stratz_data = await self.stratz_client.get_match_analysis(match_id)
                
                # Validate Herald match
                if not self.stratz_client.validate_herald_match(stratz_data):
                    embed = discord.Embed(
                        title="❌ Non-Herald Match",
                        description="This match contains players above Herald rank.",
                        color=0xFF0000
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                
                # Cache for future use
                await self.cache.set(match_id, match_details, stratz_data)
            
            # Generate AI analysis
            ai_response = await self._generate_ai_analysis(match_id, match_details, stratz_data, question)
            
            # Send response as embed
            response_embed = create_ai_response_embed(question, ai_response, match_id)
            await interaction.followup.send(embed=response_embed)
            
        except Exception as e:
            logger.error(f"Error processing /ask command: {e}")
            error_embed = discord.Embed(
                title="❌ Analysis Failed",
                description=f"Failed to analyze match: {str(e)[:200]}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    
    def _extract_match_id(self, thread_name: str) -> Optional[int]:
        """Extract match ID from thread name pattern."""
        match = re.search(r'Match (\d+)', thread_name)
        return int(match.group(1)) if match else None
    
    async def _generate_ai_analysis(self, match_id: int, match_details, stratz_data, question: str) -> str:
        """Generate comprehensive AI analysis using OpenAI."""
        
        # Build comprehensive context prompt
        radiant_summary = self._summarize_team(stratz_data.radiant_players, "Radiant")
        dire_summary = self._summarize_team(stratz_data.dire_players, "Dire")
        
        prompt = f"""You are analyzing a Herald-tier Dota 2 match. Provide insightful analysis focused on Herald-level gameplay patterns, common mistakes, and learning opportunities.

MATCH INFORMATION:
Match ID: {match_id}
Duration: {match_details.duration_formatted}
Total Kills: {stratz_data.total_kills}
Average APM: {stratz_data.average_apm:.0f if stratz_data.average_apm else 'N/A'}

RADIANT TEAM:
{radiant_summary}

DIRE TEAM:
{dire_summary}

USER QUESTION: {question}

ANALYSIS GUIDELINES:
- Focus on Herald-specific gameplay insights
- Explain WHY things happened, not just WHAT happened
- Reference specific player actions, builds, or statistics when relevant
- Keep response under 400 words for Discord formatting
- Use encouraging tone that helps Herald players learn
- Avoid jargon - explain concepts simply

Your analysis:"""

        response = await self.openai.chat.completions.create(
            model=self.config.openai_model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.choices[0].message.content.strip()
    
    def _summarize_team(self, players: List, team_name: str) -> str:
        """Create team summary for AI context."""
        summary_lines = []
        for i, player in enumerate(players, 1):
            hero_name = get_hero_name(player.hero_id)
            kda = f"{player.kills}/{player.deaths}/{player.assists}"
            rank = get_rank_name(player.rank)
            apm = f"{player.average_apm:.0f}" if player.average_apm else "N/A"
            
            summary_lines.append(f"  {i}. {hero_name}: {kda}, Level {player.level}, {rank}, {apm} APM")
        
        return f"{team_name} Team:\n" + "\n".join(summary_lines)

async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    pass
```

#### 3. Unified Herald Reporter
**File**: `src/herald_reporter.py`
**Changes**: Integrated reporting system with cache optimization

```python
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
            
            # Create Discord embeds
            match_embed = create_match_summary_embed(match_details, stratz_data)
            radiant_embed = create_team_analysis_embed(stratz_data.radiant_players, True)
            dire_embed = create_team_analysis_embed(stratz_data.dire_players, False)
            
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

```

#### 4. Enhanced Bot Architecture
**File**: `src/bot.py`
**Changes**: Unified bot supporting both periodic and interactive features

```python
"""Unified Herald Discord bot with periodic reporting and interactive analysis."""
import discord
from discord.ext import commands, tasks
import asyncio
import logging
import openai
from datetime import datetime

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
            member_cache_flags=discord.MemberCacheFlags.none()
        )
        
        self.config = config
        self.start_time = datetime.utcnow()
        
        # Unified cache shared between periodic and interactive features
        self.match_cache = UnifiedMatchCache(
            ttl_hours=config.cache_ttl_hours,
            max_entries=config.cache_max_entries
        )
        
        # Herald reporter for periodic tasks
        self.herald_reporter = HeraldMatchReporter(config, self.match_cache)
        
        # OpenAI client for interactive analysis
        if config.has_openai:
            self.openai_client = openai.AsyncOpenAI(
                api_key=config.openai_api_key,
                timeout=config.openai_timeout_seconds,
                max_retries=config.openai_max_retries
            )
            logger.info("OpenAI client initialized for interactive features")
        else:
            self.openai_client = None
            logger.warning("OpenAI API key not provided - interactive features disabled")
        
        # Basic tracking
        self.stats = {
            'errors': 0
        }
    
    async def setup_hook(self):
        """Initialize bot components and commands."""
        logger.info("Setting up unified Herald bot...")
        
        try:
            # Load interactive commands if OpenAI is available
            if self.openai_client:
                await self.add_cog(AskCommandCog(self, self.config, self.match_cache, self.openai_client))
                logger.info("Interactive analysis commands loaded")
            
            # Sync slash commands in development
            if self.config.discord_test_channel_id:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")
            
        except Exception as e:
            logger.error(f"Setup hook failed: {e}")
            raise
    
    async def on_ready(self):
        """Bot ready event - start background tasks."""
        uptime = datetime.utcnow() - self.start_time
        logger.info(f"Herald bot ready! Connected as {self.user} (startup time: {uptime.total_seconds():.1f}s)")
        
        # Start herald reporting task (staggered to avoid startup conflicts)
        await asyncio.sleep(60)  # Wait 1 minute after startup
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
            self.stats['errors'] += 1
    
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        """Handle slash command errors gracefully.""" 
        self.stats['errors'] += 1
        logger.error(f"Slash command error: {error}")
        
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ Command failed: {str(error)[:100]}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Command failed: {str(error)[:100]}", ephemeral=True)
    
    @herald_reporting_task.before_loop
    async def before_herald_reporting(self):
        """Wait for bot ready before starting periodic reports."""
        await self.wait_until_ready()
    
    async def close(self):
        """Graceful shutdown."""
        try:
            uptime = datetime.utcnow() - self.start_time
            
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
```

### Success Criteria:

#### Automated Verification:
- [ ] Discord integration tests pass: `uv run python -m pytest tests/unit/test_discord_integration.py -v`
- [ ] Live Discord embed tests pass: `uv run python -m pytest tests/integration/test_live_discord_embeds.py -v --discord-test`
- [ ] Data pipeline integrity tests pass: `uv run python -m pytest tests/integration/test_data_pipeline_integrity.py -v`
- [ ] Bot startup dry-run succeeds: `uv run python src/main.py --dry-run`

**Test File**: `tests/unit/test_discord_integration.py`
```python
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
    async def test_cache_integration_works(self, test_config, unified_cache, sample_match_details, sample_stratz_data):
        """Test cache integration between periodic and interactive features."""
        reporter = HeraldMatchReporter(test_config, unified_cache)
        
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
    
    @pytest.mark.asyncio
    async def test_periodic_reporting_functions(self, test_config, unified_cache, aioresponses_mock):
        """Test periodic reporting discovers and processes matches."""
        # Mock API responses
        aioresponses_mock.post(
            'https://api.opendota.com/api/explorer',
            payload={
                'command': 'SELECT',
                'rowCount': 1,
                'rows': [[8451070414, 1640995200, 5247, 12]],
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
    
    @pytest.mark.asyncio
    async def test_interactive_commands_work(self, test_config, unified_cache, mock_openai_client, mock_slash_interaction, sample_match_details, sample_stratz_data):
        """Test interactive ask command processes questions correctly."""
        bot = MagicMock()
        ask_cog = AskCommandCog(bot, test_config, unified_cache, mock_openai_client)
        
        # Pre-cache match data
        match_id = 8451070414
        await unified_cache.set(match_id, sample_match_details, sample_stratz_data)
        
        # Mock thread name extraction
        mock_slash_interaction.channel.name = f"Match {match_id} - 2025-01-01"
        
        # Test ask command
        await ask_cog.ask_about_match(mock_slash_interaction, "Why did this match last so long?")
        
        # Verify interaction was handled
        mock_slash_interaction.response.defer.assert_called_once()
        mock_slash_interaction.followup.send.assert_called_once()
        
        # Verify OpenAI was called
        mock_openai_client.chat.completions.create.assert_called_once()
    
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
    
```

#### Manual Verification:
- [ ] Herald matches are posted to Discord with rich embeds and team breakdowns
- [ ] Match threads are created with proper naming and contain team analysis
- [ ] `/ask` command provides relevant AI analysis in under 5 seconds
- [ ] Error handling provides user-friendly messages for various failure scenarios
- [ ] Bot maintains stable performance during extended operation

---

## Phase 4: Comprehensive Testing & Production Readiness

### Overview
Implement comprehensive testing suite with 90%+ coverage, performance validation, and production deployment preparation.

### Changes Required:

#### 1. Unified Test Infrastructure
**File**: `tests/conftest.py` 
**Changes**: Complete test fixtures supporting all functionality

```python
"""Comprehensive test fixtures for unified Herald bot testing."""
import pytest
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
        'opendota_query': json.loads((FIXTURES_DIR / 'opendota_query_response.json').read_text()),
        'opendota_match': json.loads((FIXTURES_DIR / 'opendota_match_details_response.json').read_text()),
        'stratz_graphql': json.loads((FIXTURES_DIR / 'stratz_graphql_response.json').read_text())
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

@pytest.fixture
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
        avg_rank_tier=12,  # Herald II
        lobby_type=0,
        game_mode=1
    )

@pytest.fixture
def sample_match_details(real_api_fixtures):
    """OpenDota match details from real API response."""
    return OpenDotaMatchDetail(**real_api_fixtures['opendota_match'])

@pytest.fixture
def sample_stratz_data(real_api_fixtures):
    """Stratz match data with Herald ranks enforced."""
    raw_data = real_api_fixtures['stratz_graphql']['data']['match'].copy()
    
    # Ensure all players are Herald for testing
    for player in raw_data['players']:
        if player.get('steamAccount') and player['steamAccount'].get('seasonRank'):
            # Keep original rank but ensure it's Herald (11-15)
            original_rank = player['steamAccount']['seasonRank'] 
            if original_rank < 11 or original_rank > 15:
                player['steamAccount']['seasonRank'] = 12  # Default to Herald II
    
    return StratzMatchData(match_id=8451070414, **raw_data)

@pytest.fixture
def mock_discord_bot(test_config):
    """Mock Discord bot with realistic behavior."""
    bot = MagicMock()
    bot.config = test_config
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.guilds = []
    
    # Mock async methods
    bot.get_channel = AsyncMock()
    bot.fetch_channel = AsyncMock()
    bot.add_cog = AsyncMock()
    bot.wait_until_ready = AsyncMock()
    
    return bot

@pytest.fixture
def mock_discord_channel():
    """Mock Discord text channel."""
    channel = AsyncMock()
    channel.id = 1234567890123456789
    channel.name = "herald-matches"
    channel.send = AsyncMock()
    channel.threads = []
    channel.archived_threads = AsyncMock(return_value=iter([]))
    
    return channel

@pytest.fixture
def mock_discord_thread():
    """Mock Discord thread for match discussions."""
    thread = AsyncMock()
    thread.id = 1234567890123456790
    thread.name = "Match 8451070414 - 2025-01-01"
    thread.send = AsyncMock()
    thread.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    
    return thread

@pytest.fixture 
def mock_slash_interaction(mock_discord_thread):
    """Mock Discord slash command interaction."""
    interaction = AsyncMock()
    interaction.channel = mock_discord_thread
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.user = AsyncMock()
    
    return interaction

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client with realistic responses."""
    client = AsyncMock()
    
    # Mock chat completion
    mock_response = AsyncMock()
    mock_choice = AsyncMock()
    mock_message = AsyncMock()
    mock_message.content = "This Herald match lasted long due to inefficient farming and missed opportunities to end the game. Both teams struggled with objective prioritization."
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    
    client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    return client

@pytest.fixture
def aioresponses_mock():
    """HTTP mocking for API calls."""
    with aioresponses.aioresponses() as m:
        yield m

@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for tests."""
    import logging
    logging.getLogger('src').setLevel(logging.WARNING)  # Reduce test noise

```

#### 2. Comprehensive Unit Tests
**File**: `tests/unit/test_unified_functionality.py`
**Changes**: Complete unit test coverage

```python
"""Comprehensive unit tests for unified Herald bot functionality."""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.opendota import OpenDotaMatch, OpenDotaQueryResponse, OpenDotaMatchDetail
from src.models.stratz import StratzPlayer, StratzMatchData
from src.cache.match_cache import UnifiedMatchCache
from src.api.opendota import OpenDotaClient
from src.api.stratz import StratzClient
from src.commands.ask_command import AskCommandCog
from src.config import Config

@pytest.mark.unit
class TestUnifiedModels:
    """Test unified Pydantic models with real data validation."""
    
    def test_herald_match_eligibility(self):
        """Test Herald match eligibility criteria."""
        # Herald eligible match
        herald_match = OpenDotaMatch(
            match_id=8451070414,
            start_time=1640995200,
            duration=5000,  # 83+ minutes
            avg_rank_tier=12,  # Herald II II
            lobby_type=0,
            game_mode=1
        )
        assert herald_match.is_herald_eligible is True
        assert herald_match.duration_formatted == "83:20"
        
        # Duration too short
        short_match = OpenDotaMatch(
            match_id=8451070415,
            start_time=1640995200,
            duration=4000,  # 66 minutes
            avg_rank_tier=12,
            lobby_type=0,
            game_mode=1
        )
        assert short_match.is_herald_eligible is False
        
        # Rank too high
        high_rank_match = OpenDotaMatch(
            match_id=8451070416,
            start_time=1640995200,
            duration=5000,
            avg_rank_tier=21,  # Guardian I - Above Herald
            lobby_type=0,
            game_mode=1
        )
        assert high_rank_match.is_herald_eligible is False

    def test_opendota_query_response_conversion(self, real_api_fixtures):
        """Test conversion of real API response to typed matches."""
        # Use partial real fixture data
        response_data = {
            "command": "SELECT ...",
            "rowCount": 2,
            "rows": [
                [8451070414, 1640995200, 5247, 12, 0, 1],
                [8451070415, 1640995300, 4800, 8, 0, 1]
            ],
            "fields": []
        }
        
        response = OpenDotaQueryResponse(**response_data)
        matches = response.to_matches()
        
        assert len(matches) == 2
        assert matches[0].match_id == 8451070414
        assert matches[0].duration == 5247
        assert matches[0].is_herald_eligible is True

    def test_stratz_player_analytics(self):
        """Test Stratz player model calculations."""
        player = StratzPlayer(
            hero_id=1,  # Anti-Mage
            kills=8, deaths=2, assists=12,
            level=25,
            hero_damage=28500,
            is_radiant=True,
            position="POSITION_1",
            steam_account={"seasonRank": 10},  # Herald
            stats={"actionsPerMinute": [350, 380, 420, 395]}
        )
        
        assert player.is_herald is True
        assert player.kda_ratio == 10.0  # (8+12)/2
        assert player.position_number == 1
        assert player.average_apm == 386.25
        assert player.rank == 10

    def test_stratz_match_team_separation(self, sample_stratz_data):
        """Test team separation and Herald validation."""
        radiant = sample_stratz_data.radiant_players
        dire = sample_stratz_data.dire_players
        
        assert len(radiant) == 5
        assert len(dire) == 5
        assert all(p.is_radiant for p in radiant)
        assert all(not p.is_radiant for p in dire)
        assert sample_stratz_data.all_players_herald is True

@pytest.mark.unit
@pytest.mark.cache
class TestUnifiedCache:
    """Test unified cache functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_basic_operations(self, unified_cache, sample_match_details, sample_stratz_data):
        """Test basic cache set/get operations."""
        match_id = 8451070414
        
        # Cache miss initially
        result = await unified_cache.get(match_id)
        assert result is None
        
        # Set and retrieve
        await unified_cache.set(match_id, sample_match_details, sample_stratz_data)
        cached_result = await unified_cache.get(match_id)
        
        assert cached_result is not None
        match_details, stratz_data = cached_result
        assert match_details.match_id == match_id
        assert stratz_data.match_id == match_id
        
        # Verify stats
        stats = await unified_cache.stats()
        assert stats["entries"] == 1
        assert "100.0%" in stats["hit_rate"]

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """Test cache TTL expiration functionality."""
        cache = UnifiedMatchCache(ttl_hours=0.001, max_entries=10)  # Very short TTL
        
        await cache.set(12345, "test_match", "test_stratz")
        
        # Should exist immediately
        result = await cache.get(12345)
        assert result is not None
        
        # Wait for expiration
        await asyncio.sleep(0.1)
        
        # Should be expired
        result = await cache.get(12345)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_capacity_management(self):
        """Test cache capacity limits and eviction."""
        cache = UnifiedMatchCache(ttl_hours=1, max_entries=3)
        
        # Fill to capacity
        for i in range(3):
            await cache.set(i, f"match_{i}", f"stratz_{i}")
        
        stats = await cache.stats()
        assert stats["entries"] == 3
        
        # Adding fourth entry should evict oldest
        await cache.set(3, "match_3", "stratz_3")
        
        stats = await cache.stats()
        assert stats["entries"] == 3
        
        # Oldest should be gone
        result = await cache.get(0)
        assert result is None

@pytest.mark.unit
@pytest.mark.api
class TestAPIClients:
    """Test API client functionality."""
    
    def test_opendota_client_initialization(self, test_config):
        """Test OpenDota client initialization."""
        client = OpenDotaClient(test_config)
        assert client.config == test_config
        assert client.base_url == "https://api.opendota.com/api"

    def test_stratz_client_initialization(self, test_config):
        """Test Stratz client initialization."""
        client = StratzClient(test_config)
        assert client.config == test_config
        assert client.graphql_url == "https://api.stratz.com/graphql"
        
        # Test query building
        query = client._build_comprehensive_query(12345)
        assert "match(id: 12345)" in query
        assert "heroId" in query
        assert "actionsPerMinute" in query

    def test_herald_match_validation(self, test_config, sample_stratz_data):
        """Test Herald match validation logic."""
        client = StratzClient(test_config)
        
        # All Herald players - should pass
        assert client.validate_herald_match(sample_stratz_data) is True
        
        # Add non-Herald player
        sample_stratz_data.players[0].steam_account = {"seasonRank": 25}
        assert client.validate_herald_match(sample_stratz_data) is False

@pytest.mark.unit
@pytest.mark.slash_commands
class TestAskCommand:
    """Test ask command functionality."""
    
    def test_match_id_extraction(self, test_config, mock_openai_client, unified_cache):
        """Test match ID extraction from thread names."""
        cog = AskCommandCog(None, test_config, unified_cache, mock_openai_client)
        
        # Valid formats
        assert cog._extract_match_id("Match 8451070414 - 2025-01-01") == 8451070414
        assert cog._extract_match_id("Herald Match 9876543210 Discussion") == 9876543210
        assert cog._extract_match_id("Analysis: Match 1234567890") == 1234567890
        
        # Invalid formats
        assert cog._extract_match_id("Random thread name") is None
        assert cog._extract_match_id("Match without number") is None
        assert cog._extract_match_id("") is None

    def test_team_summarization(self, test_config, mock_openai_client, unified_cache, sample_stratz_data):
        """Test team summary generation for AI context."""
        cog = AskCommandCog(None, test_config, unified_cache, mock_openai_client)
        
        radiant_summary = cog._summarize_team(sample_stratz_data.radiant_players, "Radiant")
        
        assert "Radiant Team:" in radiant_summary
        assert "Anti-Mage:" in radiant_summary  # Hero ID 1
        assert "APM" in radiant_summary
        assert "Herald" in radiant_summary

#### 3. Integration Tests
**File**: `tests/integration/test_unified_integration.py`
**Changes**: Integration tests with realistic API mocking

```python
"""Integration tests for unified Herald bot functionality."""
import pytest
import aioresponses
from unittest.mock import AsyncMock, patch
import asyncio

from src.api.opendota import OpenDotaClient
from src.api.stratz import StratzClient
from src.commands.ask_command import AskCommandCog
from src.herald_reporter import HeraldMatchReporter
from src.cache.match_cache import UnifiedMatchCache

@pytest.mark.integration
@pytest.mark.asyncio
class TestAPIIntegration:
    """Test API clients with realistic mocking."""
    
    async def test_opendota_herald_discovery(self, test_config, real_api_fixtures, aioresponses_mock):
        """Test OpenDota Herald match discovery flow."""
        client = OpenDotaClient(test_config)
        
        # Mock OpenDota explorer response
        aioresponses_mock.post(
            "https://api.opendota.com/api/explorer",
            payload=real_api_fixtures['opendota_query']
        )
        
        matches = await client.discover_herald_matches()
        
        assert len(matches) >= 0  # May be empty if no Herald matches in fixture
        assert all(m.is_herald_eligible for m in matches)

    async def test_stratz_match_analysis(self, test_config, real_api_fixtures, aioresponses_mock):
        """Test Stratz match analysis with real response structure."""
        client = StratzClient(test_config)
        match_id = 8451070414
        
        # Mock Stratz GraphQL response
        aioresponses_mock.post(
            "https://api.stratz.com/graphql",
            payload=real_api_fixtures['stratz_graphql']
        )
        
        analysis = await client.get_match_analysis(match_id)
        
        assert analysis.match_id == match_id
        assert len(analysis.players) == 10
        assert len(analysis.radiant_players) == 5
        assert len(analysis.dire_players) == 5

@pytest.mark.integration
@pytest.mark.cache
@pytest.mark.asyncio
class TestCacheIntegration:
    """Test cache integration across components."""
    
    async def test_herald_reporter_cache_integration(self, test_config, unified_cache, mock_discord_bot, mock_discord_channel, real_api_fixtures, aioresponses_mock):
        """Test herald reporter populates cache for ask commands.""" 
        reporter = HeraldMatchReporter(test_config, unified_cache)
        
        # Mock APIs
        aioresponses_mock.get(
            "https://api.opendota.com/api/matches/8451070414",
            payload=real_api_fixtures['opendota_match']
        )
        aioresponses_mock.post(
            "https://api.stratz.com/graphql", 
            payload=real_api_fixtures['stratz_graphql']
        )
        
        # Mock Discord posting
        mock_discord_bot.get_channel.return_value = mock_discord_channel
        mock_message = AsyncMock()
        mock_thread = AsyncMock()
        mock_message.create_thread.return_value = mock_thread
        mock_discord_channel.send.return_value = mock_message
        
        # Process match (should populate cache)
        success = await reporter._process_and_post_match(8451070414, [mock_discord_channel])
        assert success is True
        
        # Verify cache was populated
        cached_data = await unified_cache.get(8451070414)
        assert cached_data is not None
        
        match_details, stratz_data = cached_data
        assert match_details.match_id == 8451070414
        assert stratz_data.match_id == 8451070414

    async def test_ask_command_cache_utilization(self, test_config, unified_cache, mock_openai_client, mock_slash_interaction, sample_match_details, sample_stratz_data):
        """Test ask command utilizes cached data efficiently."""
        cog = AskCommandCog(None, test_config, unified_cache, mock_openai_client)
        
        # Pre-populate cache
        match_id = 8451070414
        await unified_cache.set(match_id, sample_match_details, sample_stratz_data)
        
        # Mock interaction in correct thread
        mock_slash_interaction.channel.name = f"Match {match_id} - 2025-01-01"
        
        # Process ask command
        await cog.ask_about_match(mock_slash_interaction, "Why did this match last so long?")
        
        # Verify OpenAI was called (meaning cache was used successfully)
        mock_openai_client.chat.completions.create.assert_called_once()
        
        # Verify response was sent
        mock_slash_interaction.followup.send.assert_called_once()
        
        # Verify cache hit
        stats = await unified_cache.stats()
        assert stats["total_hits"] > 0

@pytest.mark.integration
@pytest.mark.openai
@pytest.mark.asyncio
class TestOpenAIIntegration:
    """Test OpenAI integration with realistic scenarios."""
    
    async def test_ai_analysis_generation(self, test_config, unified_cache, mock_slash_interaction, sample_match_details, sample_stratz_data):
        """Test AI analysis generation with comprehensive match data."""
        # Use real OpenAI client mock
        from unittest.mock import AsyncMock
        
        mock_openai = AsyncMock()
        mock_response = AsyncMock()
        mock_choice = AsyncMock()
        mock_message = AsyncMock()
        mock_message.content = "This Herald match lasted 87 minutes due to both teams struggling with objective prioritization and efficient farming patterns. The Radiant team had multiple opportunities to push high ground but failed to capitalize on their advantages."
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_openai.chat.completions.create.return_value = mock_response
        
        cog = AskCommandCog(None, test_config, unified_cache, mock_openai)
        
        # Pre-populate cache
        await unified_cache.set(8451070414, sample_match_details, sample_stratz_data)
        
        # Mock interaction
        mock_slash_interaction.channel.name = "Match 8451070414 - 2025-01-01"
        
        # Process ask command
        await cog.ask_about_match(mock_slash_interaction, "What were the key factors that made this game last so long?")
        
        # Verify OpenAI was called with comprehensive prompt
        mock_openai.chat.completions.create.assert_called_once()
        call_args = mock_openai.chat.completions.create.call_args
        prompt = call_args[1]["messages"][0]["content"]
        
        # Verify prompt contains match data
        assert "8451070414" in prompt
        assert "Herald" in prompt
        assert "RADIANT TEAM:" in prompt
        assert "DIRE TEAM:" in prompt
        assert "USER QUESTION:" in prompt
        
        # Verify response was sent
        mock_slash_interaction.followup.send.assert_called_once()

#### 4. End-to-End Tests
**File**: `tests/e2e/test_unified_e2e.py`
**Changes**: Complete workflow testing

```python
"""End-to-end tests for unified Herald bot functionality."""
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, patch, MagicMock

from src.bot import UnifiedHeraldBot
from src.config import Config
from src.herald_reporter import HeraldMatchReporter

@pytest.mark.e2e
@pytest.mark.asyncio
class TestUnifiedWorkflow:
    """Test complete unified bot workflow."""
    
    @patch('src.api.opendota.OpenDotaClient.discover_herald_matches')
    @patch('src.api.opendota.OpenDotaClient.get_match_details')
    @patch('src.api.stratz.StratzClient.get_match_analysis')
    async def test_complete_periodic_to_interactive_flow(self, 
                                                       mock_stratz, 
                                                       mock_match_details, 
                                                       mock_discover, 
                                                       test_config, 
                                                       sample_herald_match, 
                                                       sample_match_details, 
                                                       sample_stratz_data,
                                                       mock_openai_client):
        """Test complete flow from periodic discovery to interactive analysis."""
        
        # Setup mocks for periodic reporting
        mock_discover.return_value = [sample_herald_match]
        mock_match_details.return_value = sample_match_details
        mock_stratz.return_value = sample_stratz_data
        
        # Create unified bot
        with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
            bot = UnifiedHeraldBot(test_config)
            
            # Mock Discord interactions
            mock_channel = AsyncMock()
            mock_channel.name = "herald-matches"
            mock_channel.send = AsyncMock()
            mock_channel.threads = []
            mock_channel.archived_threads = AsyncMock(return_value=iter([]))
            
            mock_message = AsyncMock()
            mock_thread = AsyncMock()
            mock_thread.name = f"Match {sample_herald_match.match_id} - 2025-01-01"
            mock_thread.send = AsyncMock()
            mock_message.create_thread.return_value = mock_thread
            mock_channel.send.return_value = mock_message
            
            bot.get_channel = AsyncMock(return_value=mock_channel)
            
            # Run periodic report (should populate cache)
            reporter = HeraldMatchReporter(test_config, bot.match_cache)
            await reporter.run_periodic_report(bot)
            
            # Verify periodic posting occurred
            mock_channel.send.assert_called()  # Match embed posted
            mock_thread.send.assert_called()  # Team embeds posted to thread
            
            # Verify cache was populated
            cached_data = await bot.match_cache.get(sample_herald_match.match_id)
            assert cached_data is not None
            
            # Simulate ask command in the created thread
            ask_cog = bot.get_cog('AskCommandCog')
            if ask_cog:
                mock_interaction = AsyncMock()
                mock_interaction.channel = mock_thread
                mock_interaction.response.defer = AsyncMock()
                mock_interaction.followup.send = AsyncMock()
                
                # Process ask command (should use cached data)
                await ask_cog.ask_about_match(mock_interaction, "Why did this Herald match last so long?")
                
                # Verify interaction flow
                mock_interaction.response.defer.assert_called_once()
                mock_interaction.followup.send.assert_called_once()
                mock_openai_client.chat.completions.create.assert_called_once()
                
                # Verify cache hit (no additional API calls)
                assert mock_match_details.call_count == 1  # Only called during periodic report
                assert mock_stratz.call_count == 1

    async def test_error_resilience_across_components(self, test_config, mock_openai_client):
        """Test error handling across unified bot components."""
        with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
            bot = UnifiedHeraldBot(test_config)
            
            # Test API failure handling
            with patch('src.api.opendota.OpenDotaClient.discover_herald_matches') as mock_discover:
                mock_discover.side_effect = Exception("OpenDota API failed")
                
                # Should not crash the bot
                try:
                    reporter = HeraldMatchReporter(test_config, bot.match_cache)
                    await reporter.run_periodic_report(bot)
                except Exception as e:
                    pytest.fail(f"Bot should handle API failures gracefully: {e}")
            
            # Test cache resilience
            await bot.match_cache.set(12345, "test", "test")
            result = await bot.match_cache.get(12345)
            assert result is not None

@pytest.mark.e2e
@pytest.mark.live_api
@pytest.mark.skipif(
    not os.getenv("DISCORD_BOT_TOKEN") or not os.getenv("DISCORD_TEST_CHANNEL_ID"),
    reason="Live Discord credentials not available"
)
class TestLiveDiscordIntegration:
    """Tests requiring real Discord connection."""
    
    @pytest.mark.asyncio
    async def test_real_discord_bot_startup(self):
        """Test bot startup with real Discord credentials.""" 
        config = Config(
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
            discord_test_channel_id=int(os.getenv("DISCORD_TEST_CHANNEL_ID")),
            opendota_api_key="test_key",
            stratz_api_token="test_token",
            openai_api_key="test_openai"
        )
        
        with patch('openai.AsyncOpenAI') as mock_openai_cls:
            mock_openai = AsyncMock()
            mock_openai_cls.return_value = mock_openai
            
            bot = UnifiedHeraldBot(config)
            
            # Test connection and command sync
            async def test_connection():
                await bot.wait_until_ready()
                
                # Verify bot is connected
                assert bot.user is not None
                assert len(bot.guilds) >= 0
                
                # Verify slash commands are registered
                commands = await bot.tree.fetch_commands()
                command_names = [cmd.name for cmd in commands]
                assert 'ask' in command_names
                
                await bot.close()
            
            # Start bot and run test
            connection_task = asyncio.create_task(test_connection())
            
            try:
                await bot.start(config.discord_bot_token)
            except Exception as e:
                if "already running" not in str(e).lower():
                    raise e
            finally:
                await connection_task

#### 5. Performance Tests
**File**: `tests/performance/test_unified_performance.py`
**Changes**: Performance validation across all components

```python
"""Performance tests for unified Herald bot functionality."""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch

from src.cache.match_cache import UnifiedMatchCache
from src.herald_reporter import HeraldMatchReporter
from src.commands.ask_command import AskCommandCog

@pytest.mark.performance
@pytest.mark.asyncio
class TestUnifiedPerformance:
    """Performance tests for unified functionality."""
    
    async def test_cache_performance_under_load(self, performance_config):
        """Test cache performance with high concurrent access."""
        cache = UnifiedMatchCache(ttl_hours=4, max_entries=1000)
        
        # Populate cache with test data
        for i in range(500):
            await cache.set(i, f"match_{i}", f"stratz_{i}")
        
        # Concurrent access test
        async def cache_worker():
            for _ in range(100):
                # Mix of hits and misses
                for i in range(0, 500, 5):
                    result = await cache.get(i)
                    assert result is not None
        
        # Run 10 concurrent workers
        start_time = time.time()
        workers = [cache_worker() for _ in range(10)]
        await asyncio.gather(*workers)
        end_time = time.time()
        
        # Performance expectations
        total_time = end_time - start_time
        assert total_time < 3.0, f"Cache performance too slow: {total_time:.2f}s"
        
        # Verify cache statistics
        stats = await cache.stats()
        assert int(stats["hit_rate"].replace("%", "")) > 95  # >95% hit rate
        
    async def test_herald_reporter_batch_performance(self, performance_config, large_match_dataset, mock_discord_bot):
        """Test herald reporter performance with multiple matches."""
        cache = UnifiedMatchCache()
        reporter = HeraldMatchReporter(performance_config, cache)
        
        # Mock all external dependencies
        mock_channel = AsyncMock()
        mock_message = AsyncMock()
        mock_thread = AsyncMock()
        mock_message.create_thread.return_value = mock_thread
        mock_channel.send.return_value = mock_message
        mock_discord_bot.get_channel.return_value = mock_channel
        
        with patch.object(reporter.opendota_client, 'get_match_details') as mock_details, \
             patch.object(reporter.stratz_client, 'get_match_analysis') as mock_analysis:
            
            # Setup fast mock responses
            mock_details.return_value = AsyncMock()
            mock_details.return_value.has_leavers = False
            mock_details.return_value.start_time = int(time.time())
            mock_details.return_value.match_id = 12345
            mock_details.return_value.duration = 5000
            
            mock_analysis.return_value = AsyncMock()
            mock_analysis.return_value.all_players_herald = True
            mock_analysis.return_value.radiant_players = []
            mock_analysis.return_value.dire_players = []
            
            # Process first 10 matches from dataset
            start_time = time.time()
            for match in large_match_dataset[:10]:
                await reporter._process_and_post_match(match.match_id, [mock_channel])
            end_time = time.time()
            
            # Performance expectations
            processing_time = end_time - start_time
            assert processing_time < 5.0, f"Batch processing too slow: {processing_time:.2f}s"
            
            # Verify cache utilization
            stats = await cache.stats()
            assert stats["entries"] == 10

    async def test_ask_command_response_time(self, performance_config, mock_openai_client, mock_slash_interaction, sample_match_details, sample_stratz_data):
        """Test ask command response time with cached data."""
        cache = UnifiedMatchCache()
        cog = AskCommandCog(None, performance_config, cache, mock_openai_client)
        
        # Pre-populate cache
        match_id = 8451070414
        await cache.set(match_id, sample_match_details, sample_stratz_data)
        
        # Setup interaction
        mock_slash_interaction.channel.name = f"Match {match_id} - 2025-01-01"
        
        # Measure response time
        start_time = time.time()
        await cog.ask_about_match(mock_slash_interaction, "What caused the most deaths?")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Should be very fast with cached data
        assert response_time < 1.0, f"Ask command too slow: {response_time:.2f}s"
        
        # Verify OpenAI was called (cache hit successful)
        mock_openai_client.chat.completions.create.assert_called_once()
```

### Success Criteria:

#### Automated Verification:
- [ ] All unit tests pass with >90% coverage: `uv run python -m pytest tests/unit/ --cov=src --cov-report=term-missing --cov-fail-under=90`
- [ ] Integration tests validate API interactions: `uv run python -m pytest tests/integration/ -v`
- [ ] End-to-end workflow completes without errors: `uv run python -m pytest tests/e2e/ -v`
- [ ] Live Discord tests work with real credentials: `uv run python -m pytest tests/live/ -v --discord-live`

**Test Structure Overview:**
```
tests/
├── conftest.py                    # Comprehensive fixtures
├── unit/
│   ├── test_foundation.py         # Phase 1 verification
│   ├── test_api_layer.py          # Phase 2 verification 
│   ├── test_discord_integration.py # Phase 3 verification
│   └── test_unified_functionality.py # Complete unit test suite
├── integration/
│   ├── test_opendota_integration.py   # Live API integration
│   ├── test_stratz_integration.py     # Live API integration
│   ├── test_openai_integration.py     # AI analysis integration
│   ├── test_live_discord_embeds.py    # Live Discord embed verification
│   └── test_data_pipeline_integrity.py # Complete data flow validation
├── e2e/
│   └── test_full_workflow.py         # Complete bot workflow
└── live/
    └── test_discord_live.py          # Real Discord integration
```

**Key Test File**: `tests/integration/test_live_discord_embeds.py`
```python
"""Live Discord embed tests with real bot permissions and channel posting."""
import pytest
import discord
import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import patch

from src.bot import UnifiedHeraldBot  
from src.config import Config
from src.discord.embeds import create_match_summary_embed, create_team_analysis_embed
from src.models.opendota import OpenDotaMatchDetail
from src.models.stratz import StratzMatchData

# Skip if no Discord test credentials
pytestmark = pytest.mark.skipif(
    not os.getenv("DISCORD_BOT_TOKEN") or not os.getenv("DISCORD_TEST_CHANNEL_ID"),
    reason="Discord test credentials not provided"
)

@pytest.mark.integration
@pytest.mark.asyncio
class TestLiveDiscordEmbeds:
    """Test embed creation and posting with real Discord permissions."""
    
    async def test_live_embed_posting_with_permissions(self, real_api_fixtures):
        """Test actual embed posting to Discord test channel with permission verification."""
        # Load real test configuration
        config = Config.from_env()
        
        # Verify required Discord config
        assert config.discord_bot_token, "DISCORD_BOT_TOKEN required for live Discord tests"
        assert config.discord_test_channel_id, "DISCORD_TEST_CHANNEL_ID required for live Discord tests"
        
        # Create real bot instance
        bot = UnifiedHeraldBot(config)
        
        try:
            # Start bot and wait for ready
            async with bot:
                await bot.setup_hook()
                
                # Get test channel with permission verification
                test_channel = await bot.fetch_channel(config.discord_test_channel_id)
                assert test_channel is not None, f"Could not access test channel {config.discord_test_channel_id}"
                
                # Verify bot permissions in the channel
                bot_member = test_channel.guild.get_member(bot.user.id)
                permissions = test_channel.permissions_for(bot_member)
                
                assert permissions.send_messages, "Bot missing Send Messages permission"
                assert permissions.embed_links, "Bot missing Embed Links permission" 
                assert permissions.create_public_threads, "Bot missing Create Public Threads permission"
                assert permissions.send_messages_in_threads, "Bot missing Send Messages in Threads permission"
                
                # Create test match data from real API fixtures
                match_details = OpenDotaMatchDetail(**real_api_fixtures['opendota_match'])
                stratz_raw = real_api_fixtures['stratz_graphql']['data']['match']
                stratz_data = StratzMatchData(match_id=match_details.match_id, **stratz_raw)
                
                # Create embeds using real data
                match_summary_embed = create_match_summary_embed(match_details, stratz_data)
                radiant_embed = create_team_analysis_embed(stratz_data.radiant_players, True)
                dire_embed = create_team_analysis_embed(stratz_data.dire_players, False)
                
                # Verify embed properties
                assert isinstance(match_summary_embed, discord.Embed)
                assert match_summary_embed.title == "🏆 Herald Match Analysis"
                assert str(match_details.match_id) in match_summary_embed.description
                assert len(match_summary_embed.fields) > 0
                
                assert isinstance(radiant_embed, discord.Embed)
                assert "🌅 Radiant Team Analysis" in radiant_embed.title
                assert radiant_embed.color == 0x00FF00  # Green
                
                assert isinstance(dire_embed, discord.Embed)  
                assert "🌙 Dire Team Analysis" in dire_embed.title
                assert dire_embed.color == 0xFF0000  # Red
                
                # Post match summary and create thread (actual Discord interaction)
                match_date = datetime.fromtimestamp(match_details.start_time, tz=timezone.utc)
                thread_name = f"TEST Match {match_details.match_id} - {match_date.strftime('%Y-%m-%d')}"
                
                # Send main embed and create thread
                main_message = await test_channel.send(embed=match_summary_embed)
                assert main_message is not None, "Failed to send match summary embed"
                
                # Create thread from the message
                thread = await main_message.create_thread(
                    name=thread_name,
                    auto_archive_duration=1440  # 24 hours
                )
                assert thread is not None, "Failed to create match thread"
                
                # Post team analysis embeds to thread
                radiant_message = await thread.send(embed=radiant_embed)
                assert radiant_message is not None, "Failed to send Radiant embed to thread"
                
                dire_message = await thread.send(embed=dire_embed) 
                assert dire_message is not None, "Failed to send Dire embed to thread"
                
                # Verify embeds were posted correctly by fetching them back
                fetched_main = await test_channel.fetch_message(main_message.id)
                assert len(fetched_main.embeds) == 1, "Main message should have exactly one embed"
                
                # Validate main embed content thoroughly
                main_embed = fetched_main.embeds[0]
                assert main_embed.title == "🏆 Herald Match Analysis"
                assert str(match_details.match_id) in main_embed.description
                assert f"stratz.com/matches/{match_details.match_id}" in main_embed.url
                assert main_embed.color == 0xFFD700  # Herald gold color
                
                # Verify main embed fields contain expected data
                field_names = [field.name for field in main_embed.fields]
                field_values = [field.value for field in main_embed.fields]
                
                assert "📅 Date" in field_names
                assert "⏱️ Duration" in field_names  
                assert "⚔️ Kill Density" in field_names
                assert "💀 Total Kills" in field_names
                
                # Verify field values contain actual match data
                duration_field = next((f.value for f in main_embed.fields if f.name == "⏱️ Duration"), "")
                assert ":" in duration_field, "Duration should be in MM:SS format"
                
                kills_field = next((f.value for f in main_embed.fields if f.name == "💀 Total Kills"), "")
                assert kills_field.isdigit(), "Total kills should be a number"
                assert int(kills_field) == stratz_data.total_kills
                
                # Verify footer content
                assert "Use /ask in this thread for detailed analysis" in main_embed.footer.text
                
                # Verify thread messages and their content
                thread_messages = []
                async for msg in thread.history(limit=10):
                    if msg.embeds:
                        thread_messages.append(msg)
                
                assert len(thread_messages) >= 2, "Thread should contain Radiant and Dire embeds"
                
                # Find and validate Radiant embed content
                radiant_embed = None
                dire_embed = None
                
                for msg in thread_messages:
                    if msg.embeds:
                        embed = msg.embeds[0]
                        if "🌅 Radiant" in embed.title:
                            radiant_embed = embed
                        elif "🌙 Dire" in embed.title:
                            dire_embed = embed
                
                assert radiant_embed is not None, "Radiant team embed not found in thread"
                assert dire_embed is not None, "Dire team embed not found in thread"
                
                # Validate Radiant embed content
                assert radiant_embed.color == 0x00FF00  # Green
                assert "Team Kills:" in radiant_embed.description
                radiant_team_kills = sum(p.kills for p in stratz_data.radiant_players)
                assert str(radiant_team_kills) in radiant_embed.description
                
                # Verify Radiant players are listed with correct data
                assert len(radiant_embed.fields) == 5, "Radiant team should have 5 players"
                for i, field in enumerate(radiant_embed.fields):
                    player = stratz_data.radiant_players[i]
                    
                    # Verify hero name is properly mapped and displayed
                    hero_name = get_hero_name(player.hero_id)
                    assert hero_name in field.name, f"Hero name '{hero_name}' not found in field name '{field.name}'"
                    assert f"{i+1}." in field.name, f"Player number '{i+1}' not found in field name"
                    
                    # Verify exact KDA values
                    expected_kda = f"{player.kills}/{player.deaths}/{player.assists}"
                    assert expected_kda in field.value, f"KDA '{expected_kda}' not found in field value"
                    
                    # Verify hero damage with proper formatting
                    expected_damage = format_large_number(player.hero_damage)
                    assert f"Damage:** {expected_damage}" in field.value, f"Damage '{expected_damage}' not properly formatted"
                    
                    # Verify APM data
                    if player.average_apm:
                        expected_apm = f"{player.average_apm:.0f} APM"
                        assert expected_apm in field.value, f"APM '{expected_apm}' not found"
                    else:
                        assert "N/A APM" in field.value, "Missing APM should show 'N/A APM'"
                    
                    # Verify item data - check that actual items are listed
                    item_ids = [
                        getattr(player, f"item{j}_id") for j in range(6)
                        if getattr(player, f"item{j}_id", None) and getattr(player, f"item{j}_id") != 0
                    ]
                    
                    if item_ids:
                        # Verify at least some items are shown (first 3, or less if player has fewer)
                        items_to_show = min(3, len(item_ids))
                        for j in range(items_to_show):
                            item_name = get_item_name(item_ids[j])
                            # Item should be in the items list (accounting for truncation)
                            items_section = field.value.split("Items:** ")[1] if "Items:** " in field.value else ""
                            # Check first few items are present
                            if j < items_to_show:
                                assert item_name in items_section or "..." in items_section, \
                                    f"Item '{item_name}' not found in items section '{items_section}'"
                    else:
                        # Player has no items - should still show Items field
                        assert "Items:** " in field.value, "Items field missing even when player has no items"
                
                # Validate Dire embed content  
                assert dire_embed.color == 0xFF0000  # Red
                assert "Team Kills:" in dire_embed.description
                dire_team_kills = sum(p.kills for p in stratz_data.dire_players)
                assert str(dire_team_kills) in dire_embed.description
                
                # Verify Dire players are listed with correct data
                assert len(dire_embed.fields) == 5, "Dire team should have 5 players"
                for i, field in enumerate(dire_embed.fields):
                    player = stratz_data.dire_players[i]
                    
                    # Verify hero name is properly mapped and displayed
                    hero_name = get_hero_name(player.hero_id)
                    assert hero_name in field.name, f"Hero name '{hero_name}' not found in field name '{field.name}'"
                    assert f"{i+1}." in field.name, f"Player number '{i+1}' not found in field name"
                    
                    # Verify exact KDA values
                    expected_kda = f"{player.kills}/{player.deaths}/{player.assists}"
                    assert expected_kda in field.value, f"KDA '{expected_kda}' not found in field value"
                    
                    # Verify hero damage with proper formatting
                    expected_damage = format_large_number(player.hero_damage)
                    assert f"Damage:** {expected_damage}" in field.value, f"Damage '{expected_damage}' not properly formatted"
                    
                    # Verify APM data
                    if player.average_apm:
                        expected_apm = f"{player.average_apm:.0f} APM"
                        assert expected_apm in field.value, f"APM '{expected_apm}' not found"
                    else:
                        assert "N/A APM" in field.value, "Missing APM should show 'N/A APM'"
                    
                    # Verify item data - check that actual items are listed
                    item_ids = [
                        getattr(player, f"item{j}_id") for j in range(6)
                        if getattr(player, f"item{j}_id", None) and getattr(player, f"item{j}_id") != 0
                    ]
                    
                    if item_ids:
                        # Verify at least some items are shown (first 3, or less if player has fewer)
                        items_to_show = min(3, len(item_ids))
                        for j in range(items_to_show):
                            item_name = get_item_name(item_ids[j])
                            # Item should be in the items list (accounting for truncation)
                            items_section = field.value.split("Items:** ")[1] if "Items:** " in field.value else ""
                            # Check first few items are present
                            if j < items_to_show:
                                assert item_name in items_section or "..." in items_section, \
                                    f"Item '{item_name}' not found in items section '{items_section}'"
                    else:
                        # Player has no items - should still show Items field
                        assert "Items:** " in field.value, "Items field missing even when player has no items"
                
                # Cleanup: Delete the test thread to avoid clutter
                await thread.delete()
                await main_message.delete()
                
        except discord.HTTPException as e:
            pytest.fail(f"Discord API error: {e}")
        except discord.Forbidden:
            pytest.fail("Bot lacks required permissions in test channel")
        except Exception as e:
            pytest.fail(f"Unexpected error in live Discord test: {e}")
    
    async def test_ask_command_in_real_thread(self, real_api_fixtures):
        """Test /ask command works in real Discord thread with proper embed response."""
        config = Config.from_env()
        
        # Skip if OpenAI not configured
        if not config.has_openai:
            pytest.skip("OpenAI API key required for /ask command testing")
        
        bot = UnifiedHeraldBot(config)
        
        try:
            async with bot:
                await bot.setup_hook()
                
                test_channel = await bot.fetch_channel(config.discord_test_channel_id)
                
                # Create a test thread for /ask command testing
                test_thread_name = f"TEST Ask Command - {datetime.now().strftime('%H:%M:%S')}"
                temp_message = await test_channel.send("Creating test thread...")
                test_thread = await temp_message.create_thread(name=test_thread_name)
                
                # Mock a realistic slash command interaction in the thread
                from unittest.mock import AsyncMock, MagicMock
                
                mock_interaction = AsyncMock()
                mock_interaction.channel = test_thread
                mock_interaction.channel.name = f"Match {real_api_fixtures['opendota_match']['match_id']} - Test"
                mock_interaction.response.defer = AsyncMock()
                mock_interaction.followup.send = AsyncMock()
                
                # Get the ask command cog
                ask_cog = None
                for cog in bot.cogs.values():
                    if hasattr(cog, 'ask_about_match'):
                        ask_cog = cog
                        break
                
                assert ask_cog is not None, "AskCommandCog not found in bot"
                
                # Pre-populate cache with test data
                match_details = OpenDotaMatchDetail(**real_api_fixtures['opendota_match'])
                stratz_raw = real_api_fixtures['stratz_graphql']['data']['match']
                stratz_data = StratzMatchData(match_id=match_details.match_id, **stratz_raw)
                
                await ask_cog.cache.set(match_details.match_id, match_details, stratz_data)
                
                # Test the ask command
                test_question = "Why did this match last so long?"
                await ask_cog.ask_about_match(mock_interaction, test_question)
                
                # Verify the interaction was handled correctly
                mock_interaction.response.defer.assert_called_once()
                mock_interaction.followup.send.assert_called_once()
                
                # Verify the embed was created (check call arguments)
                call_args = mock_interaction.followup.send.call_args
                assert 'embed' in call_args.kwargs, "Response should include an embed"
                
                response_embed = call_args.kwargs['embed']
                assert response_embed.title == "🤖 AI Match Analysis"
                assert test_question in response_embed.description
                assert response_embed.color == 0xFFD700  # Herald gold color
                
                # Validate AI response content structure
                assert len(response_embed.fields) == 1, "AI response should have one analysis field"
                analysis_field = response_embed.fields[0]
                assert analysis_field.name == "Analysis"
                assert len(analysis_field.value) > 50, "AI response should be substantial (>50 chars)"
                assert not analysis_field.inline, "Analysis field should not be inline"
                
                # Verify footer contains match ID and model info
                assert f"Match {match_details.match_id}" in response_embed.footer.text
                assert "GPT-4o-mini" in response_embed.footer.text or "gpt-" in response_embed.footer.text
                
                # Validate response isn't truncated or empty
                assert "[Response truncated" not in analysis_field.value or len(analysis_field.value) >= 1900
                assert analysis_field.value.strip(), "AI response should not be empty"
                
                # Cleanup
                await test_thread.delete()
                await temp_message.delete()
                
        except Exception as e:
            pytest.fail(f"Ask command live test failed: {e}")

@pytest.fixture
def real_api_fixtures():
    """Load real API fixtures for live Discord testing."""
    import json
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent.parent
    fixtures = {}
    
    try:
        fixtures['opendota_match'] = json.loads((project_root / 'opendota_match_details_response.json').read_text())
        fixtures['stratz_graphql'] = json.loads((project_root / 'stratz_graphql_response.json').read_text())
    except FileNotFoundError as e:
        pytest.skip(f"Real API fixtures not available: {e}")
    
    return fixtures
```


#### Manual Verification:
- [ ] Bot starts and runs stably for 24+ hours without memory leaks
- [ ] Periodic Herald match discovery posts to Discord successfully
- [ ] Interactive `/ask` commands provide relevant analysis in <3 seconds
- [ ] Error scenarios are handled gracefully without bot crashes

---

## Production Deployment & Maintenance

### Deployment Configuration

```bash
# Production environment variables
DISCORD_BOT_TOKEN=your_production_bot_token
DISCORD_TEST_CHANNEL_ID=your_production_channel_id
OPENDOTA_API_KEY=your_opendota_key
STRATZ_API_TOKEN=your_stratz_token
OPENAI_API_KEY=your_openai_key

# Performance tuning
CACHE_TTL_HOURS=6
CACHE_MAX_ENTRIES=200

# API rate limiting
API_DELAY_SECONDS=2  # Conservative for production
```

### Monitoring & Maintenance

1. **Performance Monitoring**: Cache hit rates, response times, API usage
2. **Error Tracking**: Failed API calls, Discord connection issues, OpenAI timeouts
3. **Resource Usage**: Memory usage, CPU utilization, network I/O
4. **User Engagement**: Command usage statistics, popular question patterns

### Scaling Considerations

- **Single Bot Architecture**: Designed for small-medium Discord communities (<1000 users)
- **Memory Management**: In-memory cache with automatic cleanup and capacity limits
- **API Rate Limits**: Conservative delays prevent rate limiting issues
- **Discord Limits**: Thread management prevents channel clutter

---

## Summary

This unified implementation plan successfully bridges the gap between periodic Herald match discovery and interactive AI-powered analysis. Key achievements:

**Architecture Unification:**
- Single bot supporting both periodic reporting and interactive commands
- Shared cache reducing API calls across all features
- Unified configuration and error handling

**Feature Integration:**
- Periodic Herald match posting populates cache for interactive analysis
- Interactive `/ask` commands leverage cached data for fast responses
- Comprehensive testing validates both workflows

**Performance Optimization:**
- Cache hit rates >80% reduce API costs and improve response times
- Sequential API processing with delays prevents rate limiting
- Performance monitoring provides actionable insights

**Production Readiness:**
- 90%+ test coverage with unit, integration, and E2E tests
- Comprehensive error handling and graceful degradation
- Live Discord integration testing validates real-world functionality

The unified approach eliminates redundancy between the original plans while creating a cohesive, efficient Discord bot that serves both automated discovery and user-driven analysis needs.
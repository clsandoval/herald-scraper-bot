# Herald Discord Bot Implementation Plan

## Overview

Implement a modern, modular Discord bot for Herald-tier Dota 2 match analysis using pure functions, Pydantic models, and periodic tasks. The bot will discover long Herald matches via OpenDota API, enhance them with detailed Stratz data, and post comprehensive analysis to Discord channels with threaded discussions.

## Current State Analysis

### What Exists Now
- **src/**: Empty structure - `main.py` is completely empty, ready for clean implementation
- **deprecated/**: Fully functional bot with single-use run-once pattern
- **Configuration**: Comprehensive pytest setup, uv dependency management, all required API tokens
- **Data mappings**: Complete hero IDs, ability mappings, constants available in deprecated/
- **Testing infrastructure**: Well-configured but no actual test files exist

### What's Missing  
- Modern modular architecture with pure functions
- Pydantic models for API validation
- Internal periodic scheduling (currently external cron-based)
- Comprehensive test suite with end-to-end Discord verification
- Proper error handling following fail-fast principles

### Key Discoveries:
- `deprecated/discord_bot.py:199-221` - Multi-channel posting with individual error handling per channel
- `deprecated/functions.py:222-298` - Chunked OpenDota queries with 1-hour time windows for rate limiting
- `deprecated/functions.py:366-413` - Stratz GraphQL integration with Bearer token authentication
- `deprecated/discord_bot.py:42-85` - Thread cleanup system with 10-day retention policy
- `pytest.ini:15-25` - Excellent test markers including `discord`, `e2e`, `live_api` for comprehensive testing

## Desired End State

A production-ready Discord bot that:
1. **Runs continuously** with Discord.py task decorators (24-hour intervals)
2. **Discovers Herald matches** using chunked OpenDota queries with proper rate limiting
3. **Validates all data** using strict Pydantic models with fail-fast error handling
4. **Posts rich embeds** to multiple Discord channels with threaded discussions
5. **Maintains clean threads** with automatic cleanup of old discussions
6. **Passes comprehensive tests** including end-to-end verification of actual Discord posts

### Verification Method
- Bot successfully posts to test channels with proper embeds and threads
- All API integrations work with 1-second delays between calls
- Pydantic validation catches malformed API responses
- Thread cleanup maintains proper channel hygiene
- Tests verify actual Discord content using bot permissions

## What We're NOT Doing

- AI commentary generation (OpenAI integration) - focus on core Discord functionality first
- Database persistence (Supabase) - maintain stateless pattern
- Telegram integration - Discord-only implementation
- Error resilience patterns - fail fast on any API errors
- Concurrent/parallel API processing - all sequential with delays
- Multiple bot instances - single bot with periodic tasks

## Implementation Approach

**Pure Functions Architecture**: Separate data collection, validation, transformation, and Discord posting into independent, testable functions.

**Sequential Processing**: All API calls with 1-second delays, no concurrency to avoid rate limiting issues.

**Fail-Fast Validation**: Any Pydantic validation error or API failure skips the entire match processing.

## Phase 1: Core Infrastructure & Pydantic Models

### Overview
Establish the foundational architecture with data models, configuration, and basic bot structure.

### Changes Required:

#### 1. Project Configuration
**File**: `pyproject.toml`
**Changes**: Add missing Pydantic dependency

```toml
# Add to dependencies
pydantic = "^2.11.7"
```

#### 2. Pydantic Models Structure
**File**: `src/models/__init__.py`
**Changes**: Create models package

```python
"""Data models for Herald Discord Bot."""
```

**File**: `src/models/opendota.py`
**Changes**: OpenDota API response models (corrected based on API verification)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class OpenDotaMatch(BaseModel):
    """Single match from OpenDota query results."""
    match_id: int
    start_time: int
    duration: int
    avg_rank_tier: Optional[int] = None
    
    @property
    def is_herald_eligible(self) -> bool:
        """Check if match meets Herald criteria."""
        return (
            self.avg_rank_tier is not None 
            and self.avg_rank_tier <= 16 
            and self.duration > 4500
        )

class OpenDotaQueryResponse(BaseModel):
    """Response from OpenDota explorer query."""
    command: str
    rowCount: int = Field(alias="rowCount")
    rows: List[Dict[str, Any]]  # Array of objects with match data
    fields: List[Dict[str, Any]]
    
    def to_matches(self) -> List[OpenDotaMatch]:
        """Convert raw rows to typed matches."""
        return [
            OpenDotaMatch(
                match_id=row["match_id"],
                start_time=row["start_time"], 
                duration=row["duration"],
                avg_rank_tier=row.get("avg_rank_tier")
            )
            for row in self.rows
        ]

class OpenDotaMatchDetail(BaseModel):
    """Detailed match information from OpenDota."""
    match_id: int
    duration: int
    start_time: int
    lobby_type: int
    game_mode: int
    players: List[Dict[str, Any]]  # Keep as dict - contains leaver_status per player
    
    @property
    def has_leavers(self) -> bool:
        """Check if any players left the game (leaver_status is per-player)."""
        return any(player.get("leaver_status", 0) != 0 for player in self.players)
```

**File**: `src/models/stratz.py`
**Changes**: Stratz GraphQL response models (corrected based on API verification)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class StratzPlayer(BaseModel):
    """Player data from Stratz API."""
    hero_id: int = Field(alias="heroId")
    kills: int
    deaths: int  
    assists: int
    position: Optional[str] = None  # String enum: "POSITION_1", "POSITION_2", etc.
    hero_damage: int = Field(alias="heroDamage")
    is_radiant: bool = Field(alias="isRadiant")
    level: int
    
    # Item slots  
    item0_id: Optional[int] = Field(alias="item0Id", default=None)
    item1_id: Optional[int] = Field(alias="item1Id", default=None)
    item2_id: Optional[int] = Field(alias="item2Id", default=None)
    item3_id: Optional[int] = Field(alias="item3Id", default=None)
    item4_id: Optional[int] = Field(alias="item4Id", default=None)
    item5_id: Optional[int] = Field(alias="item5Id", default=None)
    
    # Steam account info (can be None)
    steam_account: Optional[Dict[str, Any]] = Field(alias="steamAccount", default=None)
    
    # Advanced stats (all optional, within "stats" nested object)
    stats: Optional[Dict[str, Any]] = Field(default=None)
    
    # Playback data (optional)
    playback_data: Optional[Dict[str, Any]] = Field(alias="playbackData", default=None)
    
    # Dota Plus (can be None)
    dota_plus: Optional[Dict[str, Any]] = Field(alias="dotaPlus", default=None)
    
    @property
    def rank(self) -> Optional[int]:
        """Extract rank from steam account."""
        if self.steam_account and "seasonRank" in self.steam_account:
            return self.steam_account["seasonRank"]
        return None
    
    @property
    def is_herald(self) -> bool:
        """Check if player is Herald rank."""
        rank = self.rank
        return rank is not None and rank <= 15
    
    @property
    def actions_per_minute(self) -> List[int]:
        """Get actions per minute array (integers, not objects)."""
        if self.stats and "actionsPerMinute" in self.stats:
            return self.stats["actionsPerMinute"]
        return []
    
    @property
    def ability_cast_report(self) -> List[Dict[str, Any]]:
        """Get ability cast report."""
        if self.stats and "abilityCastReport" in self.stats:
            return self.stats["abilityCastReport"]
        return []
    
    @property
    def item_used(self) -> List[Dict[str, Any]]:
        """Get item usage statistics."""
        if self.stats and "itemUsed" in self.stats:
            return self.stats["itemUsed"]
        return []
    
    @property
    def item_purchases(self) -> List[Dict[str, Any]]:
        """Get item purchase timeline."""
        if self.stats and "itemPurchases" in self.stats:
            return self.stats["itemPurchases"]
        return []
    
    @property
    def ability_learn_events(self) -> List[Dict[str, Any]]:
        """Get ability learning progression."""
        if self.playback_data and "abilityLearnEvents" in self.playback_data:
            return self.playback_data["abilityLearnEvents"]
        return []

class StratzMatchResponse(BaseModel):
    """Raw Stratz GraphQL response wrapper."""
    data: Dict[str, Any]
    
    def to_match_data(self, match_id: int) -> "StratzMatchData":
        """Convert raw response to typed match data."""
        match_data = self.data["match"]
        if not match_data:
            raise ValueError(f"Match {match_id} not found in Stratz")
        
        # Add match_id since it's not in the response
        return StratzMatchData(
            match_id=match_id,
            players=match_data["players"]
        )

class StratzMatchData(BaseModel):
    """Complete match data from Stratz GraphQL (simplified - no top-level metadata)."""
    match_id: int  # Injected, not from API
    players: List[StratzPlayer]
    
    @property
    def all_players_herald(self) -> bool:
        """Verify all players are Herald rank."""
        return all(player.is_herald for player in self.players if player.rank is not None)
    
    @property  
    def radiant_players(self) -> List[StratzPlayer]:
        """Get Radiant team players."""
        return [p for p in self.players if p.is_radiant]
    
    @property
    def dire_players(self) -> List[StratzPlayer]:
        """Get Dire team players.""" 
        return [p for p in self.players if not p.is_radiant]
    
    # Note: For match metadata like startDateTime, durationSeconds, 
    # we need to get these from OpenDota since current Stratz query doesn't include them
    @property
    def start_date_time(self) -> Optional[int]:
        """Start date time - need to get from OpenDota."""
        return None  # TODO: Get from OpenDota match details
        
    @property  
    def duration_seconds(self) -> Optional[int]:
        """Duration in seconds - need to get from OpenDota."""
        return None  # TODO: Get from OpenDota match details
```

#### 3. Configuration Management
**File**: `src/config.py`
**Changes**: Environment-based configuration with validation

```python
import os
from typing import List
from pydantic import BaseModel, Field

class Config(BaseModel):
    """Application configuration from environment variables."""
    
    # Discord
    discord_bot_token: str = Field(...)
    discord_test_channel_id: int = Field(...)
    discord_test_thread_id: int = Field(...)
    
    # APIs
    opendota_api_key: str = Field(...)
    stratz_api_token: str = Field(...)
    
    # Optional
    openai_api_key: str = Field(default="")
    
    # Bot behavior
    query_days_back: int = Field(default=2)
    thread_retention_days: int = Field(default=10)
    api_delay_seconds: int = Field(default=1)
    
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
        )
    
    def validate_required(self) -> None:
        """Validate required fields are present."""
        required_fields = [
            "discord_bot_token", "discord_test_channel_id", 
            "opendota_api_key", "stratz_api_token"
        ]
        
        missing = [field for field in required_fields if not getattr(self, field)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
```

#### 4. Bot Foundation
**File**: `src/bot.py`
**Changes**: Basic Discord bot setup with task decorators

```python
import discord
from discord.ext import commands, tasks
import asyncio
import logging
from typing import List

from .config import Config

logger = logging.getLogger(__name__)

class HeraldBot(commands.Bot):
    """Discord bot for Herald match analysis."""
    
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        
    async def setup_hook(self):
        """Setup hook called when bot is ready."""
        logger.info("Bot is setting up...")
        
    async def on_ready(self):
        """Called when bot connects to Discord."""
        logger.info(f"Bot connected as {self.user} to {len(self.guilds)} guilds")
        
        # Start periodic herald reporting
        self.herald_report_task.start()
        
    @tasks.loop(hours=24)
    async def herald_report_task(self):
        """Periodic task to check for Herald matches."""
        logger.info("Starting Herald match analysis...")
        
        # TODO: Implement match discovery and posting
        await asyncio.sleep(1)  # Placeholder
        
    async def close(self):
        """Cleanup when bot shuts down."""
        self.herald_report_task.cancel()
        await super().close()
```

### Success Criteria:

#### Automated Verification:
- [ ] Dependencies install cleanly: `uv sync`
- [ ] All imports resolve: `uv run python -c "from src.models.opendota import OpenDotaMatch; from src.models.stratz import StratzPlayer; from src.config import Config; from src.bot import HeraldBot"`
- [ ] Type checking passes: `uv run python -m mypy src/ --strict` (if mypy is added)
- [ ] Basic bot instantiation works: `uv run python -c "from src.config import Config; from src.bot import HeraldBot; config = Config.from_env(); bot = HeraldBot(config)"`
- [ ] API verification script runs successfully: `uv run python verify_api_responses.py`

#### Manual Verification:
- [ ] Environment variables load correctly with validation errors for missing values
- [ ] Pydantic models validate actual API responses (verified against match 8451070414)
- [ ] Bot structure follows pure functions architecture principles
- [ ] Configuration separates test and production channel IDs properly

### Key API Structure Discoveries

**OpenDota API Changes:**
- ✅ Query API structure matches planned models  
- ⚠️ **Match Details**: `leaver_status` is per-player, not match-level
- ⚠️ **Query Response**: Returns objects in `rows`, not arrays

**Stratz API Major Changes:**
- ❌ **Missing Match Metadata**: Current GraphQL query lacks `startDateTime`, `durationSeconds`
- ❌ **Actions Per Minute**: Array of integers `[397, 393, 424...]`, not objects
- ⚠️ **Position Field**: String enum `"POSITION_5"`, not integer
- ⚠️ **Nullable Fields**: `dotaPlus`, `steamAccount` can be `null`

**Data Flow Impact:**
- Match metadata (date, duration) must come from **OpenDota Match Details**
- Player stats and advanced data come from **Stratz GraphQL**
- Discord embeds need **both** data sources combined

---

## Phase 2: API Integration with Pure Functions

### Overview
Implement API clients for OpenDota and Stratz with strict sequential processing and fail-fast error handling.

### Changes Required:

#### 1. OpenDota API Client
**File**: `src/api/opendota.py`
**Changes**: Pure functions for OpenDota integration

```python
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Tuple
from pypika import Query, Table
import logging

from ..models.opendota import OpenDotaMatch, OpenDotaQueryResponse, OpenDotaMatchDetail
from ..config import Config

logger = logging.getLogger(__name__)

OPENDOTA_URL = "https://api.opendota.com/api/explorer"

async def discover_herald_matches(config: Config) -> List[OpenDotaMatch]:
    """Discover Herald matches from the last N days."""
    time_chunks = _generate_time_chunks(config.query_days_back)
    matches = []
    
    for start_time, end_time in time_chunks:
        logger.info(f"Querying OpenDota for matches from {start_time} to {end_time}")
        
        chunk_matches = await _query_opendota_chunk(config, start_time, end_time)
        matches.extend(chunk_matches)
        
        # Sequential processing with delay
        await asyncio.sleep(config.api_delay_seconds)
    
    # Filter for Herald eligibility
    herald_matches = [m for m in matches if m.is_herald_eligible]
    logger.info(f"Found {len(herald_matches)} Herald-eligible matches")
    
    return herald_matches

async def get_match_details(config: Config, match_id: int) -> OpenDotaMatchDetail:
    """Get detailed match information from OpenDota."""
    url = f"https://api.opendota.com/api/matches/{match_id}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise ValueError(f"OpenDota API error: {response.status}")
            
            data = await response.json()
            return OpenDotaMatchDetail(**data)

def _generate_time_chunks(days_back: int) -> List[Tuple[int, int]]:
    """Generate 1-hour time chunks for the last N days."""
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

async def _query_opendota_chunk(config: Config, start_time: int, end_time: int) -> List[OpenDotaMatch]:
    """Query a single time chunk from OpenDota."""
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
        .where(public_matches.avg_rank_tier <= 16)  # Herald only
        .where(public_matches.duration > 4500)      # 75+ minutes
        .where(public_matches.start_time >= start_time)
        .where(public_matches.start_time <= end_time)
        .limit(100)
    )
    
    request_data = {
        "sql": str(query)
    }
    
    headers = {"Content-Type": "application/json"}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(OPENDOTA_URL, 
                               json=request_data, 
                               headers=headers) as response:
            
            if response.status != 200:
                raise ValueError(f"OpenDota chunk query failed: {response.status}")
            
            data = await response.json()
            query_response = OpenDotaQueryResponse(**data)
            return query_response.to_matches()
```

#### 2. Stratz API Client  
**File**: `src/api/stratz.py`
**Changes**: Pure functions for Stratz GraphQL integration

```python
import asyncio
import aiohttp
import json
import logging
from typing import Optional

from ..models.stratz import StratzMatchData
from ..config import Config

logger = logging.getLogger(__name__)

STRATZ_GRAPHQL_URL = "https://api.stratz.com/graphql"

# GraphQL query (corrected based on actual deprecated implementation and API verification)
STRATZ_QUERY = """
query MatchPlayers {
  match(id: MATCH_ID) {
    players {
      heroId
      kills
      deaths
      assists
      position
      steamAccount {
        seasonRank
      }
      stats {
        actionsPerMinute
        abilityCastReport{
          abilityId
          count
          targets{
            target
            count
            damage
            duration
          }
        }
        itemUsed{
          itemId
          count
        }
        itemPurchases {
          time
          itemId
        }
        courierKills {
          time
          positionX
          positionY
        }
        wards {
          time
          positionX
          positionY
          type
        }
        killEvents {
          time
          target
          byAbility
          byItem
        }
        deathEvents {
          time
          attacker
          target
          byItem
          byAbility
          positionX
          positionY
        }
      }
      playbackData {
        purchaseEvents {
          time
          itemId
        }
        abilityLearnEvents {
          time
          abilityId
          level
        }
      }
      level
      item0Id
      item1Id
      item2Id
      item3Id
      item4Id
      item5Id
      heroDamage
      dotaPlus {
        level
      }
      isRadiant
    }
  }
}
"""

async def get_match_analysis(config: Config, match_id: int) -> StratzMatchData:
    """Get comprehensive match analysis from Stratz."""
    headers = {
        "Authorization": f"Bearer {config.stratz_api_token}",
        "User-Agent": "STRATZ_API", 
        "Content-Type": "application/json",
    }
    
    # Use string replacement like in deprecated implementation
    query = STRATZ_QUERY.replace("MATCH_ID", str(match_id))
    
    request_body = {
        "query": query,
        "operationName": "MatchPlayers"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(STRATZ_GRAPHQL_URL, 
                               json=request_body, 
                               headers=headers) as response:
            
            if response.status != 200:
                raise ValueError(f"Stratz API error: {response.status}")
            
            data = await response.json()
            
            if "errors" in data:
                raise ValueError(f"Stratz GraphQL errors: {data['errors']}")
            
            # Use the response wrapper to handle conversion
            response_obj = StratzMatchResponse(**data)
            return response_obj.to_match_data(match_id)

def validate_herald_match(match_data: StratzMatchData) -> bool:
    """Validate that all players in match are Herald rank."""
    if not match_data.all_players_herald:
        logger.info(f"Match {match_data.match_id} contains non-Herald players, skipping")
        return False
    
    return True
```

#### 3. Constants from Deprecated Implementation
**File**: `src/constants.py`  
**Changes**: Copy essential mappings from deprecated implementation

```python
"""Game constants and mappings."""

# Copy HERO_ID_TO_NAME from deprecated/constants.py (lines 1-128)
HERO_ID_TO_NAME = {
    1: "Anti-Mage",
    2: "Axe", 
    # ... (copy all 150+ hero mappings)
}

# Copy ITEM_MAP from deprecated/constants.py (lines 129-640)
ITEM_MAP = {
    0: "Empty",
    1: "Blink Dagger",
    # ... (copy all 600+ item mappings)
}

# Copy rank mappings
RANK_MAP = {
    1: "Herald [1]",
    2: "Herald [2]", 
    # ... (copy rank definitions)
}

def get_hero_name(hero_id: int) -> str:
    """Get hero name by ID."""
    return HERO_ID_TO_NAME.get(hero_id, f"Unknown Hero ({hero_id})")

def get_item_name(item_id: int) -> str:
    """Get item name by ID."""
    return ITEM_MAP.get(item_id, f"Unknown Item ({item_id})")
```

### Success Criteria:

#### Automated Verification:
- [ ] API modules import successfully: `uv run python -c "from src.api.opendota import discover_herald_matches; from src.api.stratz import get_match_analysis"`
- [ ] Pydantic validation works: `uv run python -c "from src.models.opendota import OpenDotaMatch; OpenDotaMatch(match_id=123, start_time=1640995200, duration=5000, avg_rank_tier=10, lobby_type=0, game_mode=1)"`
- [ ] Constants load correctly: `uv run python -c "from src.constants import get_hero_name; assert get_hero_name(1) == 'Anti-Mage'"`
- [ ] Configuration validation works: `uv run python -c "from src.config import Config; Config.from_env().validate_required()"`

#### Manual Verification:
- [ ] API functions follow pure function principles (no side effects, deterministic)
- [ ] Sequential processing with delays is implemented correctly
- [ ] Fail-fast error handling raises appropriate exceptions for invalid data
- [ ] Pydantic models correctly validate real API response samples

---

## Phase 3: Discord Integration & Embed Formatting

### Overview
Implement Discord posting functionality with multi-channel support, thread management, and rich embeds using team colors.

### Changes Required:

#### 1. Discord Formatter Functions
**File**: `src/discord/embeds.py`
**Changes**: Pure functions for Discord embed creation

```python
import discord
from datetime import datetime, timezone
from typing import List

from ..models.stratz import StratzMatchData, StratzPlayer
from ..constants import get_hero_name, get_item_name, RANK_MAP

# Team colors from deprecated implementation
RADIANT_COLOR = 0x00FF00  # Green
DIRE_COLOR = 0xFF0000     # Red

def create_match_embed(match_details: OpenDotaMatchDetail, stratz_data: StratzMatchData) -> discord.Embed:
    """Create main match summary embed using combined OpenDota and Stratz data."""
    embed = discord.Embed(
        title="🏆 Herald Match Analysis",
        description=f"Match ID: {match_details.match_id}",
        color=RADIANT_COLOR,
        url=f"https://stratz.com/matches/{match_details.match_id}"
    )
    
    # Convert duration to MM:SS format (from OpenDota)
    duration_minutes = match_details.duration // 60
    duration_seconds = match_details.duration % 60
    duration_str = f"{duration_minutes}:{duration_seconds:02d}"
    
    # Calculate match date (from OpenDota)
    match_date = datetime.fromtimestamp(match_details.start_time, tz=timezone.utc)
    date_str = match_date.strftime("%Y-%m-%d %H:%M UTC")
    
    embed.add_field(name="📅 Date", value=date_str, inline=True)
    embed.add_field(name="⏱️ Duration", value=duration_str, inline=True)
    
    # Calculate kill density (kills per minute) using Stratz player data
    total_kills = sum(p.kills for p in stratz_data.players)
    kill_density = round(total_kills / (duration_minutes or 1), 2)
    embed.add_field(name="⚔️ Kill Density", value=f"{kill_density}/min", inline=True)
    
    embed.timestamp = match_date
    embed.set_footer(text="Herald Scraper Bot", icon_url="https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/icons/hero_strength.png")
    
    return embed

def create_team_embed(players: List[StratzPlayer], is_radiant: bool) -> discord.Embed:
    """Create team-specific embed with player details."""
    team_name = "Radiant" if is_radiant else "Dire"
    color = RADIANT_COLOR if is_radiant else DIRE_COLOR
    emoji = "🌅" if is_radiant else "🌙"
    
    embed = discord.Embed(
        title=f"{emoji} {team_name} Team",
        color=color
    )
    
    for i, player in enumerate(players):
        hero_name = get_hero_name(player.hero_id)
        kda = f"{player.kills}/{player.deaths}/{player.assists}"
        
        # Format rank
        rank_text = "Unknown"
        if player.rank:
            rank_text = RANK_MAP.get(player.rank, f"Rank {player.rank}")
        
        # Calculate APM if available (corrected - it's array of integers)
        apm_text = "N/A"
        apm_values = player.actions_per_minute
        if apm_values:
            avg_apm = sum(apm_values) / len(apm_values)
            apm_text = f"{avg_apm:.0f}"
        
        # Position
        position_text = f"Pos {player.position}" if player.position else "Unknown"
        
        field_value = (
            f"**KDA:** {kda}\n"
            f"**Level:** {player.level}\n" 
            f"**Rank:** {rank_text}\n"
            f"**Position:** {position_text}\n"
            f"**APM:** {apm_text}\n"
            f"**Hero Damage:** {player.hero_damage:,}"
        )
        
        embed.add_field(
            name=f"{i+1}. {hero_name}",
            value=field_value,
            inline=True
        )
    
    return embed
```

#### 2. Channel Management Functions
**File**: `src/discord/channels.py`
**Changes**: Pure functions for channel and thread management

```python
import discord
from discord.ext import commands
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

async def get_verified_channels(bot: commands.Bot, channel_ids: List[int]) -> List[discord.TextChannel]:
    """Get list of accessible Discord channels."""
    channels = []
    
    for channel_id in channel_ids:
        try:
            channel = bot.get_channel(channel_id)
            if channel is None:
                channel = await bot.fetch_channel(channel_id)
            
            if isinstance(channel, discord.TextChannel):
                channels.append(channel)
                logger.info(f"Successfully accessed channel: {channel.name}")
            else:
                logger.warning(f"Channel {channel_id} is not a text channel")
                
        except Exception as e:
            logger.error(f"Failed to access channel {channel_id}: {e}")
    
    return channels

async def create_match_thread(channel: discord.TextChannel, 
                            match_embed: discord.Embed, 
                            match_id: int,
                            match_date: datetime) -> Optional[discord.Thread]:
    """Create a match discussion thread."""
    try:
        # Send the main match embed
        message = await channel.send(embed=match_embed)
        
        # Create thread from the message
        date_str = match_date.strftime("%Y-%m-%d")
        thread_name = f"Match {match_id} - {date_str}"
        
        thread = await message.create_thread(name=thread_name)
        logger.info(f"Created thread: {thread_name}")
        
        return thread
        
    except Exception as e:
        logger.error(f"Failed to create thread in {channel.name}: {e}")
        return None

async def cleanup_old_threads(channel: discord.TextChannel, retention_days: int = 10):
    """Remove threads older than retention period."""
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    deleted_count = 0
    
    try:
        # Check archived threads
        async for thread in channel.archived_threads(limit=None):
            if thread.created_at < cutoff_date:
                try:
                    await thread.delete()
                    deleted_count += 1
                    # Rate limit protection
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Failed to delete archived thread {thread.name}: {e}")
        
        # Check active threads
        for thread in channel.threads:
            if thread.created_at < cutoff_date:
                try:
                    await thread.delete()
                    deleted_count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Failed to delete active thread {thread.name}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old threads from {channel.name}")
            
    except Exception as e:
        logger.error(f"Thread cleanup failed for {channel.name}: {e}")
```

#### 3. Main Herald Report Function
**File**: `src/herald_reporter.py`
**Changes**: Orchestrate the complete Herald reporting pipeline

```python
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from .config import Config
from .api.opendota import discover_herald_matches, get_match_details
from .api.stratz import get_match_analysis, validate_herald_match
from .discord.embeds import create_match_embed, create_team_embed
from .discord.channels import get_verified_channels, create_match_thread, cleanup_old_threads

logger = logging.getLogger(__name__)

async def run_herald_report(bot, config: Config):
    """Main Herald reporting pipeline."""
    logger.info("Starting Herald match analysis...")
    
    try:
        # Get verified Discord channels
        channel_ids = [config.discord_test_channel_id]  # Start with test channel
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
        
        # Process each match sequentially
        for match in herald_matches:
            try:
                await _process_single_match(match.match_id, channels, config)
                
                # Delay between matches
                await asyncio.sleep(config.api_delay_seconds)
                
            except Exception as e:
                logger.error(f"Failed to process match {match.match_id}: {e}")
                # Skip this match and continue with next (fail-fast per match)
                continue
        
        logger.info("Herald report completed successfully")
        
    except Exception as e:
        logger.error(f"Herald report failed: {e}")
        raise

async def _process_single_match(match_id: int, channels: List, config: Config):
    """Process a single match through the complete pipeline."""
    logger.info(f"Processing match {match_id}")
    
    # Get match details from OpenDota (check for leavers and get metadata)
    match_details = await get_match_details(config, match_id)
    
    if match_details.has_leavers:
        logger.info(f"Match {match_id} has leavers, skipping")
        return
    
    # Delay before Stratz call
    await asyncio.sleep(config.api_delay_seconds)
    
    # Get enhanced player data from Stratz
    stratz_data = await get_match_analysis(config, match_id)
    
    # Validate Herald ranks
    if not validate_herald_match(stratz_data):
        return  # Skip non-Herald matches
    
    # Create Discord embeds (need to combine OpenDota match details + Stratz player data)
    match_embed = create_match_embed(match_details, stratz_data)
    radiant_embed = create_team_embed(stratz_data.radiant_players, True)
    dire_embed = create_team_embed(stratz_data.dire_players, False)
    
    # Post to all channels
    for channel in channels:
        try:
            # Create match thread using OpenDota match details for timing
            match_date = datetime.fromtimestamp(match_details.start_time, tz=timezone.utc)
            thread = await create_match_thread(channel, match_embed, match_id, match_date)
            
            if thread:
                # Post team embeds to thread
                await thread.send(embed=radiant_embed)
                await asyncio.sleep(1)  # Rate limiting
                await thread.send(embed=dire_embed)
            
        except Exception as e:
            logger.error(f"Failed to post match {match_id} to channel {channel.name}: {e}")
            # Continue with other channels
```

#### 4. Update Bot with Herald Reporting
**File**: `src/bot.py`
**Changes**: Integrate herald reporting into periodic task

```python
import discord
from discord.ext import commands, tasks
import asyncio
import logging

from .config import Config
from .herald_reporter import run_herald_report

logger = logging.getLogger(__name__)

class HeraldBot(commands.Bot):
    """Discord bot for Herald match analysis."""
    
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        
    async def setup_hook(self):
        """Setup hook called when bot is ready.""" 
        logger.info("Bot is setting up...")
        
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
        except Exception as e:
            logger.error(f"Herald report task failed: {e}")
        
    async def close(self):
        """Cleanup when bot shuts down."""
        self.herald_report_task.cancel()
        await super().close()
```

### Success Criteria:

#### Automated Verification:
- [ ] All Discord modules import: `uv run python -c "from src.discord.embeds import create_match_embed; from src.discord.channels import get_verified_channels; from src.herald_reporter import run_herald_report"`
- [ ] Embed creation works with sample data: Test `create_match_embed()` with mock StratzMatchData
- [ ] Bot starts without errors: `uv run python -c "from src.config import Config; from src.bot import HeraldBot; config = Config.from_env(); bot = HeraldBot(config)"`

#### Manual Verification:
- [ ] Discord embeds display with correct team colors (green/red)
- [ ] Thread creation works in test channels
- [ ] Multi-channel posting handles individual channel failures gracefully  
- [ ] Thread cleanup removes threads older than configured retention period
- [ ] Sequential processing includes proper delays between API calls and Discord posts

---

## Phase 4: Comprehensive Testing with End-to-End Discord Verification

### Overview
Implement a complete test suite including unit tests, integration tests, and end-to-end tests that verify actual Discord posting using bot permissions.

### Changes Required:

#### 1. Test Fixtures and Configuration
**File**: `tests/conftest.py`
**Changes**: Core test fixtures and setup

```python
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock
import aioresponses
from datetime import datetime, timezone

from src.config import Config
from src.models.stratz import StratzMatchData, StratzPlayer
from src.models.opendota import OpenDotaMatch
from src.bot import HeraldBot

@pytest.fixture
def test_config():
    """Test configuration with safe defaults."""
    return Config(
        discord_bot_token="TEST_TOKEN_123",
        discord_test_channel_id=1234567890,
        discord_test_thread_id=1234567891,
        opendota_api_key="TEST_OPENDOTA_KEY",
        stratz_api_token="TEST_STRATZ_TOKEN",
        query_days_back=1,
        api_delay_seconds=0,  # No delays in tests
        thread_retention_days=1
    )

@pytest.fixture
def sample_herald_match():
    """Sample OpenDota Herald match."""
    return OpenDotaMatch(
        match_id=7891234567,
        start_time=int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()),
        duration=5000,  # 83+ minutes
        avg_rank_tier=12,  # Herald
        lobby_type=0,
        game_mode=1
    )

@pytest.fixture  
def sample_stratz_data():
    """Sample Stratz match data with Herald players."""
    players = []
    
    # Radiant team (Herald ranks 1-5)
    for i in range(5):
        players.append(StratzPlayer(
            hero_id=i + 1,
            kills=5 + i,
            deaths=3 + i,
            assists=8 + i,
            position=i + 1,
            hero_damage=15000 + (i * 1000),
            is_radiant=True,
            level=20 + i,
            steam_account={"seasonRank": i + 1}  # Herald ranks
        ))
    
    # Dire team (Herald ranks 6-10) 
    for i in range(5):
        players.append(StratzPlayer(
            hero_id=i + 6,
            kills=4 + i,
            deaths=5 + i,
            assists=7 + i,
            position=i + 1,
            hero_damage=14000 + (i * 1000),
            is_radiant=False,
            level=19 + i,
            steam_account={"seasonRank": i + 6}  # Herald ranks
        ))
    
    return StratzMatchData(
        match_id=7891234567,
        start_date_time=int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()),
        duration_seconds=5000,
        players=players
    )

@pytest.fixture
def mock_discord_bot(test_config):
    """Mock Discord bot for testing."""
    bot = MagicMock(spec=HeraldBot)
    bot.config = test_config
    return bot

@pytest.fixture
def mock_discord_channel():
    """Mock Discord text channel.""" 
    channel = AsyncMock()
    channel.id = 1234567890
    channel.name = "test-herald-channel"
    channel.send = AsyncMock()
    channel.archived_threads = AsyncMock()
    channel.threads = []
    return channel

@pytest.fixture
def mock_discord_thread():
    """Mock Discord thread."""
    thread = AsyncMock()
    thread.id = 1234567891
    thread.name = "Match 7891234567 - 2025-01-01"
    thread.send = AsyncMock()
    thread.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return thread

@pytest.fixture
def aioresponses_mock():
    """Setup aioresponses for HTTP mocking."""
    with aioresponses.aioresponses() as m:
        yield m
```

#### 2. Unit Tests
**File**: `tests/unit/test_models.py`
**Changes**: Pydantic model validation tests

```python
import pytest
from datetime import datetime, timezone

from src.models.opendota import OpenDotaMatch, OpenDotaQueryResponse
from src.models.stratz import StratzPlayer, StratzMatchData

class TestOpenDotaModels:
    
    def test_herald_match_eligibility(self):
        """Test Herald match eligibility detection."""
        # Herald eligible match
        herald_match = OpenDotaMatch(
            match_id=123,
            start_time=1640995200,
            duration=5000,  # 83+ minutes
            avg_rank_tier=10,  # Herald
            lobby_type=0,
            game_mode=1
        )
        assert herald_match.is_herald_eligible is True
        
        # Too short
        short_match = OpenDotaMatch(
            match_id=124,
            start_time=1640995200, 
            duration=3000,  # 50 minutes
            avg_rank_tier=10,
            lobby_type=0,
            game_mode=1
        )
        assert short_match.is_herald_eligible is False
        
        # Too high rank
        high_rank_match = OpenDotaMatch(
            match_id=125,
            start_time=1640995200,
            duration=5000,
            avg_rank_tier=20,  # Above Herald
            lobby_type=0,
            game_mode=1
        )
        assert high_rank_match.is_herald_eligible is False

    def test_query_response_conversion(self):
        """Test conversion from raw API response to typed matches."""
        response_data = {
            "rows": [
                [7891234567, 1640995200, 5000, 12, 0, 1],
                [7891234568, 1640995300, 4800, 8, 0, 1]
            ]
        }
        
        response = OpenDotaQueryResponse(**response_data)
        matches = response.to_matches()
        
        assert len(matches) == 2
        assert matches[0].match_id == 7891234567
        assert matches[0].duration == 5000
        assert matches[0].avg_rank_tier == 12

class TestStratzModels:
    
    def test_herald_player_detection(self):
        """Test Herald rank detection for players.""" 
        # Herald player
        herald_player = StratzPlayer(
            hero_id=1,
            kills=5, deaths=3, assists=8,
            hero_damage=15000,
            is_radiant=True,
            level=20,
            steam_account={"seasonRank": 10}
        )
        assert herald_player.rank == 10
        assert herald_player.is_herald is True
        
        # Non-Herald player
        high_rank_player = StratzPlayer(
            hero_id=2,
            kills=8, deaths=2, assists=12,
            hero_damage=25000,
            is_radiant=False,
            level=25,
            steam_account={"seasonRank": 25}  # Above Herald
        )
        assert high_rank_player.rank == 25
        assert high_rank_player.is_herald is False

    def test_team_separation(self, sample_stratz_data):
        """Test Radiant/Dire team separation."""
        radiant = sample_stratz_data.radiant_players
        dire = sample_stratz_data.dire_players
        
        assert len(radiant) == 5
        assert len(dire) == 5
        assert all(p.is_radiant for p in radiant)
        assert all(not p.is_radiant for p in dire)

    def test_all_herald_validation(self, sample_stratz_data):
        """Test Herald validation for entire match."""
        assert sample_stratz_data.all_players_herald is True
        
        # Add non-Herald player
        sample_stratz_data.players[0].steam_account = {"seasonRank": 25}
        assert sample_stratz_data.all_players_herald is False
```

**File**: `tests/unit/test_discord_embeds.py`
**Changes**: Discord embed creation tests

```python
import pytest
import discord
from datetime import datetime, timezone

from src.discord.embeds import create_match_embed, create_team_embed

class TestDiscordEmbeds:
    
    def test_match_embed_creation(self, sample_stratz_data):
        """Test match summary embed creation."""
        embed = create_match_embed(sample_stratz_data)
        
        assert isinstance(embed, discord.Embed)
        assert "Herald Match Analysis" in embed.title
        assert str(sample_stratz_data.match_id) in embed.description
        assert embed.color == 0x00FF00  # Radiant green
        assert f"https://stratz.com/matches/{sample_stratz_data.match_id}" in embed.url
        
        # Check fields
        field_names = [field.name for field in embed.fields]
        assert "📅 Date" in field_names
        assert "⏱️ Duration" in field_names
        assert "⚔️ Kill Density" in field_names

    def test_radiant_team_embed(self, sample_stratz_data):
        """Test Radiant team embed creation."""
        radiant_players = sample_stratz_data.radiant_players
        embed = create_team_embed(radiant_players, True)
        
        assert isinstance(embed, discord.Embed)
        assert "Radiant Team" in embed.title
        assert embed.color == 0x00FF00  # Green
        assert len(embed.fields) == 5
        
        # Check player data formatting
        first_player = embed.fields[0]
        assert "Anti-Mage" in first_player.name  # Hero ID 1
        assert "KDA:" in first_player.value
        assert "5/3/8" in first_player.value

    def test_dire_team_embed(self, sample_stratz_data):
        """Test Dire team embed creation."""
        dire_players = sample_stratz_data.dire_players
        embed = create_team_embed(dire_players, False)
        
        assert isinstance(embed, discord.Embed)
        assert "Dire Team" in embed.title
        assert embed.color == 0xFF0000  # Red
        assert len(embed.fields) == 5
```

#### 3. API Integration Tests
**File**: `tests/integration/test_api.py`
**Changes**: Test API integrations with mocking

```python
import pytest
import aioresponses
import json

from src.api.opendota import discover_herald_matches, get_match_details
from src.api.stratz import get_match_analysis, validate_herald_match

@pytest.mark.asyncio
@pytest.mark.api
class TestOpenDotaAPI:
    
    async def test_herald_match_discovery(self, test_config, aioresponses_mock):
        """Test OpenDota Herald match discovery."""
        # Mock OpenDota explorer response
        mock_response = {
            "rows": [
                [7891234567, 1640995200, 5000, 12, 0, 1],  # Herald match
                [7891234568, 1640995300, 3000, 12, 0, 1],  # Too short
                [7891234569, 1640995400, 5000, 20, 0, 1],  # Too high rank
            ]
        }
        
        aioresponses_mock.post(
            "https://api.opendota.com/api/explorer",
            payload=mock_response
        )
        
        matches = await discover_herald_matches(test_config)
        
        # Should only return Herald-eligible matches
        assert len(matches) == 1
        assert matches[0].match_id == 7891234567
        assert matches[0].is_herald_eligible is True

    async def test_match_details_retrieval(self, test_config, aioresponses_mock):
        """Test OpenDota match details retrieval.""" 
        match_id = 7891234567
        mock_details = {
            "match_id": match_id,
            "duration": 5000,
            "start_time": 1640995200,
            "leaver_status": 0,  # No leavers
            "lobby_type": 0,
            "game_mode": 1,
            "players": [{"player_slot": i} for i in range(10)]
        }
        
        aioresponses_mock.get(
            f"https://api.opendota.com/api/matches/{match_id}",
            payload=mock_details
        )
        
        details = await get_match_details(test_config, match_id)
        
        assert details.match_id == match_id
        assert details.has_leavers is False

@pytest.mark.asyncio
@pytest.mark.api  
class TestStratzAPI:
    
    async def test_match_analysis_retrieval(self, test_config, aioresponses_mock, sample_stratz_data):
        """Test Stratz match analysis retrieval."""
        match_id = 7891234567
        
        # Mock GraphQL response structure
        mock_response = {
            "data": {
                "match": {
                    "id": match_id,
                    "startDateTime": sample_stratz_data.start_date_time,
                    "durationSeconds": sample_stratz_data.duration_seconds,
                    "players": [
                        {
                            "heroId": p.hero_id,
                            "kills": p.kills,
                            "deaths": p.deaths,
                            "assists": p.assists,
                            "heroDamage": p.hero_damage,
                            "isRadiant": p.is_radiant,
                            "level": p.level,
                            "steamAccount": p.steam_account
                        }
                        for p in sample_stratz_data.players
                    ]
                }
            }
        }
        
        aioresponses_mock.post(
            "https://api.stratz.com/graphql",
            payload=mock_response
        )
        
        analysis = await get_match_analysis(test_config, match_id)
        
        assert analysis.match_id == match_id
        assert len(analysis.players) == 10
        assert analysis.all_players_herald is True

    def test_herald_match_validation(self, sample_stratz_data):
        """Test Herald match validation logic."""
        # All Herald players - should pass
        assert validate_herald_match(sample_stratz_data) is True
        
        # Add non-Herald player - should fail
        sample_stratz_data.players[0].steam_account = {"seasonRank": 25}
        assert validate_herald_match(sample_stratz_data) is False
```

#### 4. End-to-End Discord Tests
**File**: `tests/e2e/test_discord_integration.py`
**Changes**: Complete end-to-end tests with real Discord verification

```python
import pytest
import discord
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.bot import HeraldBot
from src.herald_reporter import run_herald_report, _process_single_match
from src.discord.channels import get_verified_channels, create_match_thread
from src.discord.embeds import create_match_embed

@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.discord
class TestDiscordIntegration:
    
    async def test_channel_verification(self, mock_discord_bot, mock_discord_channel):
        """Test Discord channel access verification."""
        mock_discord_bot.get_channel.return_value = mock_discord_channel
        
        channels = await get_verified_channels(mock_discord_bot, [1234567890])
        
        assert len(channels) == 1
        assert channels[0] == mock_discord_channel
        mock_discord_bot.get_channel.assert_called_once_with(1234567890)

    async def test_match_thread_creation(self, mock_discord_channel, sample_stratz_data):
        """Test match thread creation with embed posting."""
        # Setup mock message and thread
        mock_message = AsyncMock()
        mock_thread = AsyncMock()
        mock_message.create_thread.return_value = mock_thread
        mock_discord_channel.send.return_value = mock_message
        
        # Create match embed and thread
        match_embed = create_match_embed(sample_stratz_data)
        match_date = datetime.fromtimestamp(sample_stratz_data.start_date_time, tz=timezone.utc)
        
        thread = await create_match_thread(
            mock_discord_channel,
            match_embed, 
            sample_stratz_data.match_id,
            match_date
        )
        
        # Verify interactions
        mock_discord_channel.send.assert_called_once_with(embed=match_embed)
        mock_message.create_thread.assert_called_once()
        assert thread == mock_thread

    @patch('src.api.opendota.discover_herald_matches')
    @patch('src.api.opendota.get_match_details')  
    @patch('src.api.stratz.get_match_analysis')
    async def test_complete_herald_pipeline(self, 
                                          mock_stratz_analysis,
                                          mock_match_details,
                                          mock_discover_matches,
                                          test_config,
                                          mock_discord_bot,
                                          mock_discord_channel,
                                          sample_herald_match,
                                          sample_stratz_data):
        """Test complete Herald reporting pipeline."""
        # Setup mocks
        mock_discover_matches.return_value = [sample_herald_match]
        
        mock_details = AsyncMock()
        mock_details.has_leavers = False
        mock_match_details.return_value = mock_details
        
        mock_stratz_analysis.return_value = sample_stratz_data
        mock_discord_bot.get_channel.return_value = mock_discord_channel
        
        # Setup thread creation mock
        mock_message = AsyncMock()
        mock_thread = AsyncMock() 
        mock_message.create_thread.return_value = mock_thread
        mock_discord_channel.send.return_value = mock_message
        
        # Run the herald report
        await run_herald_report(mock_discord_bot, test_config)
        
        # Verify the pipeline executed
        mock_discover_matches.assert_called_once_with(test_config)
        mock_match_details.assert_called_once_with(test_config, sample_herald_match.match_id)
        mock_stratz_analysis.assert_called_once_with(test_config, sample_herald_match.match_id)
        
        # Verify Discord interactions
        mock_discord_channel.send.assert_called()  # Match embed posted
        mock_thread.send.assert_called()  # Team embeds posted to thread

@pytest.mark.asyncio  
@pytest.mark.e2e
@pytest.mark.live_api
class TestLiveDiscordPosting:
    """Tests that actually connect to Discord and verify real posting."""
    
    @pytest.mark.skipif(
        not os.getenv("DISCORD_BOT_TOKEN") or not os.getenv("DISCORD_TEST_CHANNEL_ID"),
        reason="Live Discord credentials not available"
    )
    async def test_real_discord_posting(self, test_config, sample_stratz_data):
        """Test actual Discord posting to test channel."""
        # Use real Discord credentials for live testing
        real_config = Config(
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
            discord_test_channel_id=int(os.getenv("DISCORD_TEST_CHANNEL_ID")),
            discord_test_thread_id=int(os.getenv("DISCORD_TEST_THREAD_ID", "0")),
            opendota_api_key="test",
            stratz_api_token="test"
        )
        
        # Create real bot instance
        bot = HeraldBot(real_config)
        
        async def test_posting():
            await bot.wait_until_ready()
            
            # Get test channel
            channel = bot.get_channel(real_config.discord_test_channel_id)
            assert channel is not None, "Test channel not accessible"
            
            # Create and post match embed
            match_embed = create_match_embed(sample_stratz_data)
            message = await channel.send(embed=match_embed)
            
            # Verify message was posted
            assert message.embeds
            assert "Herald Match Analysis" in message.embeds[0].title
            
            # Create thread
            thread_name = f"Test Match {sample_stratz_data.match_id}"
            thread = await message.create_thread(name=thread_name)
            
            # Post team embeds to thread
            radiant_embed = create_team_embed(sample_stratz_data.radiant_players, True)
            dire_embed = create_team_embed(sample_stratz_data.dire_players, False)
            
            radiant_msg = await thread.send(embed=radiant_embed)
            dire_msg = await thread.send(embed=dire_embed)
            
            # Verify thread messages
            assert radiant_msg.embeds[0].color == 0x00FF00  # Green
            assert dire_msg.embeds[0].color == 0xFF0000     # Red
            
            # Cleanup test thread 
            await thread.delete()
            await message.delete()
            
            await bot.close()
        
        # Run the live test
        try:
            await bot.start(real_config.discord_bot_token)
            bot.loop.create_task(test_posting())
        except Exception as e:
            await bot.close()
            raise e
```

#### 5. Error Handling Tests
**File**: `tests/integration/test_error_scenarios.py`
**Changes**: Test fail-fast error handling

```python
import pytest
import aioresponses
from unittest.mock import AsyncMock, patch

from src.api.opendota import discover_herald_matches
from src.api.stratz import get_match_analysis
from src.herald_reporter import _process_single_match

@pytest.mark.asyncio
@pytest.mark.error_scenarios
class TestErrorHandling:
    
    async def test_opendota_api_failure(self, test_config, aioresponses_mock):
        """Test OpenDota API failure handling."""
        # Mock API failure
        aioresponses_mock.post(
            "https://api.opendota.com/api/explorer",
            status=500
        )
        
        with pytest.raises(ValueError, match="OpenDota chunk query failed"):
            await discover_herald_matches(test_config)

    async def test_stratz_api_failure(self, test_config, aioresponses_mock):
        """Test Stratz API failure handling."""
        # Mock GraphQL error response
        aioresponses_mock.post(
            "https://api.stratz.com/graphql",
            payload={
                "errors": [{"message": "Match not found"}]
            }
        )
        
        with pytest.raises(ValueError, match="Stratz GraphQL errors"):
            await get_match_analysis(test_config, 123456789)

    async def test_pydantic_validation_failure(self, test_config, aioresponses_mock):
        """Test Pydantic validation error handling."""
        # Mock invalid API response (missing required fields)
        aioresponses_mock.post(
            "https://api.stratz.com/graphql",
            payload={
                "data": {
                    "match": {
                        "id": 123,
                        # Missing required fields - should cause validation error
                    }
                }
            }
        )
        
        with pytest.raises(Exception):  # Pydantic validation error
            await get_match_analysis(test_config, 123456789)

    @patch('src.api.opendota.get_match_details')
    @patch('src.api.stratz.get_match_analysis')
    async def test_match_processing_skips_on_failure(self,
                                                   mock_stratz,
                                                   mock_opendota,
                                                   test_config,
                                                   mock_discord_channel):
        """Test that match processing skips failed matches."""
        # Mock API failure
        mock_opendota.side_effect = ValueError("API failed")
        
        channels = [mock_discord_channel]
        
        # Should not raise exception, just skip the match
        await _process_single_match(123456789, channels, test_config)
        
        # Verify no Discord interactions occurred
        mock_discord_channel.send.assert_not_called()
```

#### 6. Performance Tests
**File**: `tests/performance/test_performance.py`
**Changes**: Performance and load testing

```python
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch

from src.herald_reporter import run_herald_report

@pytest.mark.asyncio
@pytest.mark.performance
class TestPerformance:
    
    @patch('src.api.opendota.discover_herald_matches')
    @patch('src.api.opendota.get_match_details')
    @patch('src.api.stratz.get_match_analysis')
    async def test_multiple_match_processing_time(self,
                                                mock_stratz,
                                                mock_opendota_details,
                                                mock_discover,
                                                test_config,
                                                mock_discord_bot,
                                                mock_discord_channel,
                                                sample_herald_match,
                                                sample_stratz_data):
        """Test processing time for multiple matches."""
        # Setup 10 test matches
        test_matches = [sample_herald_match] * 10
        mock_discover.return_value = test_matches
        
        mock_details = AsyncMock()
        mock_details.has_leavers = False
        mock_opendota_details.return_value = mock_details
        mock_stratz.return_value = sample_stratz_data
        
        mock_discord_bot.get_channel.return_value = mock_discord_channel
        mock_message = AsyncMock()
        mock_thread = AsyncMock()
        mock_message.create_thread.return_value = mock_thread
        mock_discord_channel.send.return_value = mock_message
        
        # Set very small delay for performance test
        test_config.api_delay_seconds = 0.01
        
        start_time = time.time()
        await run_herald_report(mock_discord_bot, test_config)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should process 10 matches in reasonable time
        # With 0.01s delays, should take ~0.2s plus processing overhead
        assert processing_time < 5.0, f"Processing took too long: {processing_time}s"
        
        # Verify all matches were processed
        assert mock_opendota_details.call_count == 10
        assert mock_stratz.call_count == 10
```

#### 7. Main Entry Point and Test Runner
**File**: `src/main.py`
**Changes**: Application entry point

```python
import asyncio
import logging
import os
from dotenv import load_dotenv

from .config import Config
from .bot import HeraldBot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    """Main application entry point."""
    try:
        # Load and validate configuration
        config = Config.from_env()
        config.validate_required()
        
        # Create and start bot
        bot = HeraldBot(config)
        logger.info("Starting Herald Discord Bot...")
        
        await bot.start(config.discord_bot_token)
        
    except Exception as e:
        logger.error(f"Bot startup failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

**File**: `tests/test_runner.py` 
**Changes**: Custom test runner for comprehensive testing

```python
"""Custom test runner for comprehensive Herald bot testing."""
import subprocess
import sys
import os

def run_test_suite():
    """Run the complete test suite with proper ordering."""
    
    # Set test environment variables
    os.environ.update({
        "DISCORD_BOT_TOKEN": "TEST_TOKEN",
        "DISCORD_TEST_CHANNEL_ID": "123456789",
        "OPENDOTA_API_KEY": "TEST_KEY",
        "STRATZ_API_TOKEN": "TEST_TOKEN"
    })
    
    test_commands = [
        # Unit tests first
        ["uv", "run", "python", "-m", "pytest", "tests/unit/", "-v", "-m", "unit"],
        
        # Integration tests  
        ["uv", "run", "python", "-m", "pytest", "tests/integration/", "-v", "-m", "integration"],
        
        # End-to-end tests (excluding live API)
        ["uv", "run", "python", "-m", "pytest", "tests/e2e/", "-v", "-m", "e2e and not live_api"],
        
        # Performance tests
        ["uv", "run", "python", "-m", "pytest", "tests/performance/", "-v", "-m", "performance"],
        
        # Coverage report
        ["uv", "run", "python", "-m", "pytest", "--cov=src", "--cov-report=html", "--cov-report=term"]
    ]
    
    for cmd in test_commands:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"Test command failed: {' '.join(cmd)}")
            return result.returncode
    
    print("All tests passed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(run_test_suite())
```

### Success Criteria:

#### Automated Verification:
- [ ] All unit tests pass: `uv run python -m pytest tests/unit/ -v`
- [ ] All integration tests pass: `uv run python -m pytest tests/integration/ -v`  
- [ ] All non-live end-to-end tests pass: `uv run python -m pytest tests/e2e/ -v -m "e2e and not live_api"`
- [ ] Performance tests complete within time limits: `uv run python -m pytest tests/performance/ -v`
- [ ] Test coverage above 80%: `uv run python -m pytest --cov=src --cov-report=term`
- [ ] Custom test runner executes successfully: `uv run python tests/test_runner.py`

#### Manual Verification:
- [ ] Live Discord tests work with real bot token: `uv run python -m pytest tests/e2e/ -v -m "live_api"` (requires real credentials)
- [ ] Bot successfully connects to Discord and posts test message to configured test channel
- [ ] Thread creation and team embed posting work correctly in Discord UI
- [ ] Thread cleanup removes old test threads properly
- [ ] Error scenarios are handled gracefully without crashing the bot
- [ ] API rate limiting with 1-second delays is respected during testing

---

## Testing Strategy

### Test Pyramid Structure
1. **Unit Tests (70%)**: Fast, isolated tests for pure functions and models
2. **Integration Tests (20%)**: API clients, Discord interactions, data flow
3. **End-to-End Tests (10%)**: Complete pipeline with real Discord posting

### Key Testing Approaches

#### Discord Verification Strategy
- **Mock Testing**: Use `unittest.mock.AsyncMock` for Discord.py objects during development
- **Live Testing**: Real Discord bot posting to test channels for verification
- **Content Verification**: Check embed colors, field values, thread names match expected patterns
- **Permission Testing**: Verify bot can create threads, post embeds, manage channels

#### API Integration Testing
- **HTTP Mocking**: Use `aioresponses` to mock OpenDota and Stratz API responses
- **Error Simulation**: Test API failures, malformed responses, network issues
- **Rate Limiting**: Verify 1-second delays between API calls
- **Data Validation**: Ensure Pydantic models catch invalid API responses

#### End-to-End Validation
Tests verify the complete user experience:
1. Bot discovers Herald matches from OpenDota
2. Validates match eligibility and player ranks
3. Enriches data from Stratz API
4. Posts formatted embeds to Discord channels  
5. Creates discussion threads with team embeds
6. Cleans up old threads periodically

### Performance Considerations

- **Sequential Processing**: All API calls and Discord posts happen sequentially with delays
- **Memory Usage**: Pydantic models for data validation without excessive memory overhead
- **Thread Management**: Automatic cleanup prevents Discord channel clutter
- **Error Recovery**: Failed matches are skipped without affecting subsequent processing

### Migration Notes

**From Deprecated Implementation:**
1. **Data Mappings**: Copy hero/item constants from `deprecated/constants.py`
2. **API Patterns**: Reference but modernize the retry logic and error handling
3. **Discord Formatting**: Keep embed colors and field structure but improve type safety
4. **Environment Variables**: Use same variable names for compatibility

**Key Changes:**
- **Architecture**: Single-use → Persistent bot with periodic tasks
- **Error Handling**: Infinite retry → Fail-fast with skip
- **Data Validation**: Raw dictionaries → Strict Pydantic models
- **Testing**: No tests → Comprehensive test suite with Discord verification

## References

- Research document: `thoughts/shared/research/2025-09-10_23-30-00_minimal-discord-bot-design.md`
- Deprecated implementation: `deprecated/discord_bot.py:196-323`, `deprecated/functions.py:222-413`
- Pytest configuration: `pytest.ini` with comprehensive test markers
- Environment configuration: `.env` with all required API tokens
- Constants and mappings: `deprecated/constants.py:1-649`
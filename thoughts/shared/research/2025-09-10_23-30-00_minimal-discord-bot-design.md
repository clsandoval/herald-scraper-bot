---
date: 2025-09-10T23:30:00-08:00
researcher: Claude
git_commit: b05df5f249ec312bfbeecc00624eaa40072053dd
branch: revamp
repository: herald-scraper-bot
topic: "Minimal Discord Bot with Pydantic Models and Periodic Tasks"
tags: [research, codebase, discord, pydantic, api-integration, herald-scraper]
status: complete
last_updated: 2025-09-10
last_updated_by: Claude
---

# Research: Minimal Discord Bot with Pydantic Models and Periodic Tasks

**Date**: 2025-09-10T23:30:00-08:00  
**Researcher**: Claude  
**Git Commit**: b05df5f249ec312bfbeecc00624eaa40072053dd  
**Branch**: revamp  
**Repository**: herald-scraper-bot

## Research Question

How to create a simple, minimal Discord bot using pure functions, strict Pydantic models for API validation, and periodic task execution that replicates the exact query and filter logic from both OpenDota and Stratz APIs as implemented in the deprecated Herald Scraper Bot?

## Summary

The Herald Scraper Bot codebase provides excellent foundation patterns for creating a minimal, function-based Discord bot. The deprecated implementation shows comprehensive API integration patterns while the current project structure offers a clean slate for implementing modern practices with Pydantic validation. Key findings reveal the project uses sophisticated concurrent API queries with chunked time processing for OpenDota and comprehensive GraphQL queries for Stratz, with rich Discord embed formatting.

## Detailed Findings

### Project Structure and Current State

#### Current Implementation Status
- **Active codebase**: Minimal structure with empty `src/main.py` and basic `src/__init__.py`
- **Dependencies ready**: `discord.py >= 2.6.3`, `aiohttp >= 3.12.15`, `openai >= 1.106.1` already configured
- **Pydantic available**: v2.11.7 installed but **not actively used** - needs to be added to `pyproject.toml`
- **Testing framework**: Comprehensive pytest setup with async support

#### Project Structure (`C:\Users\armor\OneDrive\Desktop\cs\herald-scraper-bot\`)
```
├── src/                    # Clean slate for new implementation
├── deprecated/             # Legacy working implementation
├── tests/                  # Test framework ready
├── pyproject.toml         # UV-based dependency management
├── pytest.ini            # Comprehensive test configuration
└── .env                   # Environment variables
```

### API Integration Patterns

#### OpenDota API Implementation (`deprecated/functions.py:222-298`)
**Core Features**:
- **Concurrent chunked queries**: Splits time ranges into 1-hour chunks for rate limiting
- **Herald-specific filtering**: `avg_rank_tier <= 16`, `duration > 4500` (75+ min games)
- **Async processing**: Uses `aiohttp.ClientSession` with `asyncio.gather()` for parallel requests
- **SQL query generation**: Uses pypika for structured queries to OpenDota explorer endpoint

**Filter Logic**:
```python
# Key filters for Herald matches
.where(public_matches.avg_rank_tier <= 16)  # Herald tier only
.where(public_matches.duration > 4500)      # Long games (75+ minutes)
.where(public_matches.start_time >= chunk_start)
.where(public_matches.start_time <= chunk_end)
```

**Error Handling**: Infinite retry with 60-second backoff for OpenDota failures

#### Stratz GraphQL API Implementation (`deprecated/functions.py:366-413`)
**Authentication**: Bearer token with custom headers for GraphQL
**Comprehensive Data Query**: Single GraphQL query retrieves:
- Player stats (KDA, position, rank, hero damage, level)
- Detailed analytics (APM per minute, ability casts, item usage)
- Timeline events (kills, deaths, purchases, ward placement)
- Playback data (skill build progression)

**Query Structure** (`deprecated/functions.py:107-192`):
- Main query: `STRATZ_QUERY` for complete match analysis
- Simplified query: `STRATZ_INFO` for basic match info
- Complex nested structure capturing all match details

### Discord Bot Implementation Patterns (`deprecated/discord_bot.py`)

#### Bot Architecture
- **Run-once execution model**: Bot executes task in `on_ready()` then shuts down
- **Multi-channel support**: Hardcoded channel list for posting to multiple Discord channels
- **Thread-based organization**: Creates message threads for detailed match discussions
- **Rich embed formatting**: Structured embeds with team colors and comprehensive data

#### Key Discord.py Patterns
- `discord.Intents.default()` with `message_content = True`
- `commands.Bot` framework (though no commands implemented)
- Embed creation with color coding (Radiant: `0x00FF00`, Dire: `0xFF0000`)
- Thread management including automated cleanup of old threads (>10 days)

#### Error Handling
- Per-channel error isolation for multi-channel posting
- Discord API error handling (`Forbidden`, `NotFound`)
- Rate limiting with `asyncio.sleep(2)` between messages

### Data Transformation and Validation Needs

#### Missing Pydantic Models (Currently Raw Dictionary Access)
The deprecated code shows clear patterns that need Pydantic validation:

**Player Data Structure** (`deprecated/functions.py:443-465`):
```python
# Current raw dictionary approach - needs Pydantic models
heroes = [{
    "name": HERO_ID_TO_NAME[x["heroId"]],
    "position": x["position"] if x["position"] else "Not Provided",
    "kills": x["kills"], "deaths": x["deaths"], "assists": x["assists"],
    "damage_done": x["heroDamage"],
    "rank": (x["steamAccount"]["seasonRank"]),
    "items": [/* item array */],
    "isRadiant": x["isRadiant"],
} for x in stratz_data]
```

**Complex Nested API Responses** (`deprecated/functions.py:556-750`):
- Deep nested dictionary access without validation
- Manual null checking throughout
- Risk of KeyError exceptions
- Inconsistent data structure handling

### Periodic Task Execution

#### Current Approach (deprecated)
- **External scheduling**: `fly.toml` shows `sleep 86400` (daily execution)
- **Run-once pattern**: Bot starts, executes task, shuts down
- **Simple timing**: External cron-like scheduler vs Discord.py task decorators

#### Task Flow
1. **Match Discovery**: OpenDota chunked queries → Herald matches
2. **Enhanced Analysis**: Stratz GraphQL → Complete match data  
3. **Data Processing**: Format/transform → Structured analysis
4. **Discord Posting**: Create embeds → Post to channels → Create threads

### Constants and Configuration

#### Data Mappings (`deprecated/constants.py`)
- `HERO_ID_TO_NAME`: 128 hero mappings (lines 1-128)
- `ITEM_MAP`: 640+ item mappings (lines 129-640)  
- `RANK_MAP`: Herald tier mappings (lines 643-649)
- Separate `ability_ids.json` for ability name resolution

#### Environment Variables
- **Required**: `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`
- **API tokens**: `STRATZ_API_TOKEN`, `OPENAI_API_KEY`
- **Optional**: Telegram integration tokens

## Code References

- `deprecated/discord_bot.py:196-323` - Main herald report function with Discord integration
- `deprecated/functions.py:222-298` - Concurrent OpenDota API queries with chunking  
- `deprecated/functions.py:366-413` - Stratz GraphQL integration with authentication
- `deprecated/functions.py:526-749` - Data transformation and formatting pipeline
- `deprecated/constants.py:1-649` - Game data mappings for heroes, items, ranks
- `pyproject.toml` - Modern UV-based dependency configuration

## Architecture Insights

### Pure Function Design Opportunities
1. **Stateless API clients**: Separate functions for OpenDota and Stratz queries
2. **Data transformation pipeline**: Pure functions for raw API data → validated Pydantic models
3. **Discord formatter functions**: Pure functions taking validated data → Discord embeds
4. **Modular execution**: Separate data collection from Discord posting

### Pydantic Model Design Needs
1. **OpenDota Models**: Match search results with rows of match IDs, more detailed API calls per match ID
2. **Stratz GraphQL Models**: Complex nested player/match data with optional fields

### Periodic Task Implementation Options
1. **External scheduler** (current approach): Cron/systemd calling bot script
2. **Discord.py tasks extension**: `@tasks.loop()` decorators for internal scheduling

## Open Questions - ANSWERED

1. **Task scheduling preference**: External vs internal Discord.py task decorators?
   - **ANSWER**: Use Discord.py task decorators for internal scheduling

2. **Data persistence**: Current implementation is stateless - maintain this pattern?
   - **ANSWER**: Yes, maintain stateless pattern

3. **Error resilience**: How to handle partial failures in multi-channel posting?
   - **ANSWER**: No try/except blocks or fallbacks - any API failures should skip the match entirely

4. **Rate limiting**: Current manual delays vs discord.py built-in rate limiting?
   - **ANSWER**: Use 1-second delays between each API call, no batching - all sequential processing

5. **Configuration management**: Environment variables vs configuration files?
   - **ANSWER**: Use environment variables only

### Required Environment Variables

```

```

## Recommendations

### Immediate Implementation Steps
1. **Add Pydantic to dependencies**: Update `pyproject.toml` to include `pydantic`
2. **Create model structure**: Design Pydantic models for API responses with strict validation
3. **Implement pure API functions**: Separate OpenDota and Stratz clients with 1-second delays
4. **Build Discord formatter**: Pure functions for embed creation
5. **Add periodic scheduling**: Use Discord.py `@tasks.loop()` decorators for internal scheduling
6. **Update environment variables**: Add all required API keys and Discord configuration

### Architecture Principles - UPDATED
- **Pure functions**: All data transformation should be stateless
- **Strict validation**: Pydantic models for all external API data - **fail fast on validation errors**
- **No error resilience**: Skip matches entirely on any API failures - no try/except or fallbacks
- **Sequential processing**: 1-second delays between API calls, no batching or concurrent requests
- **Modular design**: Separate concerns (API, validation, formatting, posting)
- **Environment-based config**: All configuration through environment variables only
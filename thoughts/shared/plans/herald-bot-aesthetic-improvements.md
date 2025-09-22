# Herald Bot Aesthetic Improvements Implementation Plan

## Overview

Implement comprehensive aesthetic and functional improvements to Herald bot's Discord presentation while maintaining the current three-embed structure. Enhancements include immediate formatting fixes, visual optimizations, AI-powered match highlights, and advanced item timing displays.

## Current State Analysis

### Existing Architecture
- **Three-embed system**: Match Summary (gold) + Radiant Team (green) + Dire Team (red)
- **Character usage**: Well within Discord limits (~300-1200 chars per embed vs 6,000 limit)
- **Current posting sequence**: Main channel embed → thread creation → team embeds → AI instructions

### Key Issues Identified
- **Player field formatting**: `inline=True` at `src/discord/embeds.py:104` causes horizontal cramming
- **Item truncation**: Shows only first 3 items with "..." at `src/discord/embeds.py:95`
- **Visual clutter**: Excessive emoji usage and poor information density
- **Missing insights**: No contextual match analysis or item timing information

### Key Discoveries
- **Separate message strategy**: Each embed gets full 6,000 character budget since sent separately
- **Strong foundation**: Robust data pipeline from OpenDota → Stratz → Discord
- **Testing infrastructure**: `tests/live/test_discord_posting.py` ready for visual validation

## Desired End State

After implementation completion:
- **Improved readability**: Each player displays vertically with full item inventories
- **Enhanced aesthetics**: Condensed formatting with refined color scheme and minimal emoji usage
- **AI-powered insights**: Automated match highlights with Herald-specific humor and analysis
- **Complete item information**: Full 6-item inventories displayed for each player

### Verification Methods
- Visual testing via existing test framework shows improved embed layouts
- Character count validation ensures optimal space utilization
- User feedback confirms better readability and information value
- Cost monitoring validates LLM integration stays under $1/month

## What We're NOT Doing

- **Architecture changes**: Maintaining current three-embed structure
- **Slash command modifications**: Keeping existing `/ask` command functionality unchanged
- **Mobile-first design**: Desktop experience remains primary focus
- **Complex item selection**: No LLM-based item filtering, just showing full inventories
- **Item timing features**: No purchase timing displays or strategic item analysis
- **Advanced optimizations**: No caching systems or user configuration options
- **Real-time features**: No live match updates or streaming integration
- **Database changes**: No modifications to existing data models or caching

## Implementation Approach

**Strategy**: Incremental improvements with immediate wins first, progressing to AI-enhanced features. Each phase builds on previous foundations while maintaining backward compatibility and system stability.

**Key Principles**:
- Preserve existing three-embed posting sequence
- Enhance information density without visual clutter
- Add AI features with graceful degradation
- Maintain Herald-focused humor and insights

## Phase 1: Immediate Formatting Fixes

### Overview
Critical readability improvements that can be implemented in under 30 minutes with immediate visual impact.

### Changes Required

#### 1. Player Field Layout Fix
**File**: `src/discord/embeds.py`
**Lines**: 104
**Change**: Fix horizontal player cramming

```python
# Current (line 104):
embed.add_field(name=f"{i}. {hero_name}", value=field_value, inline=True)

# Fixed:
embed.add_field(name=f"{i}. {hero_name}", value=field_value, inline=False)
```

#### 2. Complete Item Inventory Display
**File**: `src/discord/embeds.py`
**Lines**: 89-95
**Change**: Show all 6 items instead of truncated first 3

```python
# Current (lines 89-95):
items = []
for j in range(6):
    item_id = getattr(player, f"item{j}Id", None)
    if item_id and item_id != 0:
        items.append(get_item_name(item_id))

items_text = ", ".join(items[:3]) + ("..." if len(items) > 3 else "")

# Enhanced:
items = []
for j in range(6):
    item_id = getattr(player, f"item{j}Id", None)
    if item_id and item_id != 0:
        items.append(get_item_name(item_id))

items_text = ", ".join(items) if items else "No items"
```

### Success Criteria

#### Automated Verification:
- [ ] Code passes type checking: `uv run python -m mypy src/discord/embeds.py`
- [ ] Unit tests pass: `uv run python -m pytest tests/discord_bot/test_embeds.py -v`
- [ ] No linting errors: `uv run python -m ruff check src/discord/embeds.py`

#### Manual Verification:
- [ ] Visual test shows each player on separate line: `uv run python tests/live/test_discord_posting.py`
- [ ] All player items display completely without truncation
- [ ] Embed layout remains clean and readable
- [ ] No visual regressions in match summary or team analysis embeds

---

## Phase 2: Aesthetic Enhancements

### Overview
Visual optimizations to reduce clutter, improve information density, and create better visual hierarchy while staying within Discord's generous character limits.

### Changes Required

#### 1. Emoji Reduction and Refinement
**File**: `src/discord/embeds.py`
**Lines**: Multiple locations
**Strategy**: Remove decorative emojis, keep functional ones

```python
# Current match summary (lines 28, 39, 41, 52, 54):
title="🏆 Herald Match Analysis"
name="📅 Date"
name="⏱️ Duration"
name="⚔️ Kill Density"
name="💀 Total Kills"

# Refined:
title="Herald Match Analysis"
name="Date"
name="Duration"
name="Kill Density"
name="Total Kills"

# Keep team emojis for visual distinction:
# 🌅 Radiant Team Analysis (functional)
# 🌙 Dire Team Analysis (functional)
```

#### 2. Condensed Field Formatting
**File**: `src/discord/embeds.py`
**Lines**: 97-102
**Change**: Optimize player field information density

```python
# Current format (lines 97-102):
field_value = (
    f"**KDA:** {kda}\n"
    f"**Damage:** {format_large_number(player.heroDamage)}\n"
    f"**APM:** {apm_info}\n"
    f"**Items:** {items_text}"
)

# Condensed format (33% space reduction):
field_value = (
    f"**{kda}** • {format_large_number(player.heroDamage)} dmg • {apm_info}\n"
    f"**Items:** {items_text}"
)
```

#### 3. Color Scheme Refinement
**File**: `src/discord/embeds.py`
**Lines**: 17-20
**Change**: Subtle color adjustments for better visual hierarchy

```python
# Current colors:
RADIANT_COLOR = 0x00FF00  # Bright green
DIRE_COLOR = 0xFF0000     # Bright red
HERALD_COLOR = 0xFFD700   # Gold

# Refined colors (maintaining team distinction):
RADIANT_COLOR = 0x92C5F7  # Softer blue-green
DIRE_COLOR = 0xFF6B6B     # Softer red
HERALD_COLOR = 0xF39C12   # Warmer gold
```

### Success Criteria

#### Automated Verification:
- [ ] Embeds render without errors: `uv run python tests/live/test_discord_posting.py`
- [ ] Character counts remain well under limits (validate <2000 per embed)
- [ ] All tests pass: `uv run python -m pytest tests/discord_bot/ -v`
- [ ] Color constants properly imported: `uv run python -c "from src.discord.embeds import RADIANT_COLOR, DIRE_COLOR, HERALD_COLOR; print('Colors loaded')"`

#### Manual Verification:
- [ ] Visual clutter significantly reduced compared to Phase 1 output
- [ ] Information density improved while maintaining readability
- [ ] Color scheme provides better visual hierarchy
- [ ] Team distinction remains clear with refined colors

---

## Phase 3: AI-Powered Match Highlights

### Overview
Add LLM-generated match analysis as a plain Discord message providing Herald-specific insights, unusual plays, and entertaining observations about match quirks.

### Changes Required

#### 1. LLM Integration Function
**File**: `src/services/match_analysis.py` (new file)
**Purpose**: Pure function for AI-powered match highlight generation

```python
"""AI-powered match analysis functions for generating Herald match highlights."""

import os
from typing import Optional
from openai import AsyncOpenAI
from ..models.stratz import StratzMatchData
from ..models.opendota import OpenDotaMatchDetail
from ..constants import get_hero_name, get_item_name, get_ability_name, get_rank_name, format_duration, format_large_number

async def generate_match_highlights(
    match_details: OpenDotaMatchDetail,
    stratz_data: StratzMatchData
) -> Optional[str]:
    """Generate entertaining Herald-specific match highlights."""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    client = AsyncOpenAI(api_key=api_key)
    context = _build_match_context(match_details, stratz_data)

    prompt = """
    Analyze this Herald-tier Dota 2 match and create entertaining bullet points highlighting the most notable/ridiculous moments.

    You have access to comprehensive timing data including exact purchase times and ability usage patterns. Focus on:

    **Purchase Timing Analysis:**
    - Major items bought at unusual times (e.g., "Blink Dagger @45m", "BKB @8m")
    - Role confusion through item purchases (cores buying wards late, supports buying carries)
    - Extremely late or early major item acquisitions
    - Suspicious purchase patterns that indicate poor game sense

    **Ability & Behavioral Analysis:**
    - APM anomalies with specific minute ranges (0 APM stretches, extreme spikes)
    - Underused abilities (especially ultimates used only once in long games)
    - Spam clicking patterns (300+ casts of basic abilities)
    - Never-used abilities that should be core to the hero

    **Herald-Specific Patterns:**
    - Economic inefficiency (gold earned vs spent patterns)
    - Performance benchmark extremes (top/bottom 10% in any stat)
    - Team coordination failures evidenced by timing data
    - Late-game item builds that make no sense for game state

    Format as markdown bullet points. Be humorous but not mean-spirited. Include specific timings and statistics when available.
    Start with: "## 📝 Herald Match Insights (With Precise Timing Data)"

    Use the comprehensive timing data to create insights that go beyond surface-level observations.
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": context}
            ],
            max_tokens=800,
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception:
        # Graceful degradation
        return None

def _build_match_context(match_details: OpenDotaMatchDetail, stratz_data: StratzMatchData) -> str:
    """Build comprehensive match context for AI analysis including ALL available data."""
    from datetime import datetime

    # Basic match info
    context_parts = [
        f"Match ID: {match_details.match_id}",
        f"Duration: {format_duration(match_details.duration)}",
        f"Start Time: {datetime.fromtimestamp(match_details.start_time).strftime('%Y-%m-%d %H:%M:%S')}",
        f"Winner: {'Radiant' if match_details.radiant_win else 'Dire'}",
        f"Game Mode: {match_details.game_mode}",
        f"Lobby Type: {match_details.lobby_type}",
        f"Patch: {getattr(match_details, 'patch', 'Unknown')}",
        f"Region: {getattr(match_details, 'region', 'Unknown')}",
        f"Cluster: {getattr(match_details, 'cluster', 'Unknown')}",
        f"Total Kills: {stratz_data.total_kills}",
        f"Radiant Score: {getattr(match_details, 'radiant_score', 'N/A')}",
        f"Dire Score: {getattr(match_details, 'dire_score', 'N/A')}",
        f"Has Leavers: {match_details.has_leavers}",
        ""
    ]

    # Combine player data from both APIs
    opendota_players = {p.get("player_slot", 0): p for p in match_details.players}

    context_parts.append("=== DETAILED PLAYER ANALYSIS ===")
    context_parts.append("")

    for i, stratz_player in enumerate(stratz_data.players, 1):
        # Find corresponding OpenDota player data
        slot = i - 1 if stratz_player.isRadiant else (i - 6) + 128
        opendota_player = opendota_players.get(slot, {})

        # Basic info
        hero_name = get_hero_name(stratz_player.heroId)
        team = "Radiant" if stratz_player.isRadiant else "Dire"
        kda = f"{stratz_player.kills}/{stratz_player.deaths}/{stratz_player.assists}"

        context_parts.append(f"Player {i}: {hero_name} ({team})")

        # Core stats
        context_parts.append(f"  KDA: {kda} (Ratio: {stratz_player.kda_ratio:.2f})")
        context_parts.append(f"  Level: {stratz_player.level or opendota_player.get('level', 'N/A')}")
        context_parts.append(f"  Position: {stratz_player.position or 'Unknown'}")

        # Damage and performance
        context_parts.append(f"  Hero Damage: {format_large_number(stratz_player.heroDamage)}")
        if 'hero_healing' in opendota_player:
            context_parts.append(f"  Hero Healing: {format_large_number(opendota_player['hero_healing'])}")
        if 'tower_damage' in opendota_player:
            context_parts.append(f"  Tower Damage: {format_large_number(opendota_player['tower_damage'])}")

        # Economic stats from OpenDota
        if 'gold_per_min' in opendota_player:
            context_parts.append(f"  GPM: {opendota_player['gold_per_min']}")
        if 'xp_per_min' in opendota_player:
            context_parts.append(f"  XPM: {opendota_player['xp_per_min']}")
        if 'last_hits' in opendota_player:
            context_parts.append(f"  Last Hits: {opendota_player['last_hits']}")
        if 'denies' in opendota_player:
            context_parts.append(f"  Denies: {opendota_player['denies']}")
        if 'net_worth' in opendota_player:
            context_parts.append(f"  Net Worth: {format_large_number(opendota_player['net_worth'])}")

        # APM data from Stratz
        if stratz_player.average_apm:
            apm_data = stratz_player.actions_per_minute
            min_apm = min(apm_data) if apm_data else 0
            max_apm = max(apm_data) if apm_data else 0
            context_parts.append(f"  APM: {stratz_player.average_apm:.0f} avg (range: {min_apm}-{max_apm})")

            # APM anomalies detection
            if apm_data:
                zero_minutes = sum(1 for apm in apm_data if apm == 0)
                if zero_minutes > 0:
                    context_parts.append(f"  ⚠️ APM Anomaly: {zero_minutes} minutes with 0 APM")
                if max_apm > 300:
                    context_parts.append(f"  ⚠️ APM Anomaly: Peak of {max_apm} APM (unusually high)")

        # Rank information
        if stratz_player.rank:
            rank_name = get_rank_name(stratz_player.rank)
            context_parts.append(f"  Rank: {rank_name} ({stratz_player.rank})")
        elif 'rank_tier' in opendota_player and opendota_player['rank_tier']:
            rank_name = get_rank_name(opendota_player['rank_tier'])
            context_parts.append(f"  Rank: {rank_name} ({opendota_player['rank_tier']})")

        # Items (complete inventory)
        items = []

        # Main items (Stratz has priority)
        for j in range(6):
            item_id = getattr(stratz_player, f"item{j}Id", None)
            if not item_id and f"item_{j}" in opendota_player:
                item_id = opendota_player[f"item_{j}"]
            if item_id and item_id != 0:
                items.append(get_item_name(item_id))

        # Backpack items from OpenDota
        backpack_items = []
        for j in range(3):
            backpack_key = f"backpack_{j}"
            if backpack_key in opendota_player and opendota_player[backpack_key]:
                backpack_items.append(get_item_name(opendota_player[backpack_key]))

        # Neutral items
        neutral_items = []
        if 'item_neutral' in opendota_player and opendota_player['item_neutral']:
            neutral_items.append(get_item_name(opendota_player['item_neutral']))
        if 'item_neutral2' in opendota_player and opendota_player['item_neutral2']:
            neutral_items.append(get_item_name(opendota_player['item_neutral2']))

        context_parts.append(f"  Items: {', '.join(items) if items else 'No items'}")
        if backpack_items:
            context_parts.append(f"  Backpack: {', '.join(backpack_items)}")
        if neutral_items:
            context_parts.append(f"  Neutral Items: {', '.join(neutral_items)}")

        # Purchase timing data from Stratz (if available in raw data)
        # Note: This requires accessing raw Stratz GraphQL response data
        # The current StratzPlayer model doesn't include purchaseEvents
        # This would need to be passed separately or the model extended
        if hasattr(stratz_player, 'purchase_events') and stratz_player.purchase_events:
            # Raw purchase timing data available for AI analysis
            purchase_count = len([p for p in stratz_player.purchase_events if p.get('time', 0) >= 0])
            if purchase_count > 0:
                context_parts.append(f"  Purchase Events Available: {purchase_count} items tracked with precise timing")

        # Special items/upgrades from OpenDota
        upgrades = []
        if opendota_player.get('aghanims_scepter'):
            upgrades.append("Aghanim's Scepter")
        if opendota_player.get('aghanims_shard'):
            upgrades.append("Aghanim's Shard")
        if opendota_player.get('moonshard'):
            upgrades.append("Consumed Moonshard")
        if upgrades:
            context_parts.append(f"  Special Upgrades: {', '.join(upgrades)}")

        # Ability build from OpenDota
        if 'ability_upgrades_arr' in opendota_player:
            ability_upgrades = opendota_player['ability_upgrades_arr']
            if ability_upgrades:
                ability_names = [get_ability_name(ability_id) for ability_id in ability_upgrades[:10]]  # First 10 skills
                context_parts.append(f"  Skill Build (first 10): {' → '.join(ability_names)}")

        # Ability usage data from Stratz (if available)
        # Note: This requires accessing raw Stratz GraphQL response data
        # The current StratzPlayer model doesn't include abilityCastReport
        if hasattr(stratz_player, 'ability_cast_report') and stratz_player.ability_cast_report:
            # Raw ability usage data for AI analysis
            ability_usage = []
            for ability_report in stratz_player.ability_cast_report:
                ability_id = ability_report.get('abilityId')
                cast_count = ability_report.get('count', 0)
                ability_name = get_ability_name(ability_id)
                ability_usage.append(f"{ability_name}: {cast_count} casts")

            if ability_usage:
                context_parts.append(f"  Ability Usage: {', '.join(ability_usage)}")

        # Player behavior indicators
        if 'leaver_status' in opendota_player and opendota_player['leaver_status'] != 0:
            context_parts.append(f"  ⚠️ Leaver Status: {opendota_player['leaver_status']}")

        # Performance benchmarks (OpenDota provides percentiles)
        if 'benchmarks' in opendota_player:
            benchmarks = opendota_player['benchmarks']
            notable_benchmarks = []

            for stat, data in benchmarks.items():
                if isinstance(data, dict) and 'pct' in data:
                    pct = data['pct']
                    if pct < 0.1:  # Bottom 10%
                        notable_benchmarks.append(f"{stat}: {pct:.1%} (very low)")
                    elif pct > 0.9:  # Top 10%
                        notable_benchmarks.append(f"{stat}: {pct:.1%} (very high)")

            if notable_benchmarks:
                context_parts.append(f"  Notable Performance: {'; '.join(notable_benchmarks)}")

        # Gold efficiency
        if all(key in opendota_player for key in ['gold_spent', 'net_worth']):
            total_gold = opendota_player['gold_spent'] + opendota_player.get('gold', 0)
            context_parts.append(f"  Gold Stats: {format_large_number(total_gold)} earned, {format_large_number(opendota_player['gold_spent'])} spent")

        context_parts.append("")  # Separator between players

    # Match-wide statistics
    context_parts.append("=== MATCH STATISTICS ===")
    context_parts.append(f"Average Match APM: {stratz_data.average_apm:.0f}" if stratz_data.average_apm else "Average APM: N/A")
    context_parts.append(f"All Players Herald Rank: {stratz_data.all_players_herald}")

    # Team totals
    radiant_kills = sum(p.kills for p in stratz_data.radiant_players)
    dire_kills = sum(p.kills for p in stratz_data.dire_players)
    radiant_damage = sum(p.heroDamage for p in stratz_data.radiant_players)
    dire_damage = sum(p.heroDamage for p in stratz_data.dire_players)

    context_parts.append(f"Team Kills - Radiant: {radiant_kills}, Dire: {dire_kills}")
    context_parts.append(f"Team Damage - Radiant: {format_large_number(radiant_damage)}, Dire: {format_large_number(dire_damage)}")

    return "\n".join(context_parts)


```

#### 2. Stratz API Enhancement (Required for Timing Data)
**File**: `src/api/stratz.py`
**Purpose**: Modify Stratz GraphQL query to include timing data

```python
# Update the GraphQL query to include purchaseEvents and abilityCastReport:
STRATZ_MATCH_QUERY = """
query GetMatch($matchId: Long!) {
  match(id: $matchId) {
    players {
      heroId
      kills
      deaths
      assists
      level
      heroDamage
      isRadiant
      position
      steamAccount {
        seasonRank
      }
      stats {
        actionsPerMinute
      }
      item0Id
      item1Id
      item2Id
      item3Id
      item4Id
      item5Id
      # NEW: Add timing data
      purchaseEvents {
        time
        itemId
      }
      abilityCastReport {
        abilityId
        count
        targets {
          target
          count
          damage
          duration
        }
      }
      playbackData {
        # Additional timing data if needed
        abilityUpgradeEvents {
          time
          abilityId
        }
      }
    }
  }
}
"""
```

#### 3. Enhanced Stratz Model
**File**: `src/models/stratz.py`
**Purpose**: Extend StratzPlayer model to include timing data

```python
# Add these fields to StratzPlayer class:
from typing import List, Optional, Dict, Any

class PurchaseEvent(BaseModel):
    """Individual purchase event with timing."""
    time: int
    itemId: int = Field(alias="itemId")

class AbilityCast(BaseModel):
    """Ability cast statistics."""
    abilityId: int = Field(alias="abilityId")
    count: int
    targets: Optional[List[Dict[str, Any]]] = None

class StratzPlayer(BaseModel):
    # ... existing fields ...

    # NEW: Timing data fields
    purchase_events: Optional[List[PurchaseEvent]] = Field(alias="purchaseEvents", default=None)
    ability_cast_report: Optional[List[AbilityCast]] = Field(alias="abilityCastReport", default=None)

```

#### 4. Integration into Herald Reporter
**File**: `src/herald_reporter.py`
**Lines**: Add after line 110 (after embed creation)
**Change**: Generate and post AI highlights with enhanced timing data

```python
# Add import at top:
from .services.match_analysis import generate_match_highlights

# After embed creation (around line 110):
# Generate AI highlights with comprehensive timing data
highlights = await generate_match_highlights(match_details, stratz_data)

# Update posting sequence in _post_to_discord:
# 1. Post match summary (creates thread) - existing
# 2. Post team embeds - existing
# 3. Post AI highlights if available
if highlights:
    await asyncio.sleep(1)  # Rate limiting
    await thread.send(highlights)

# 4. Post AI instructions - existing
```

#### 3. Enhanced Stratz Model (Optional Extension)
**File**: `src/models/stratz.py`
**Purpose**: Extend StratzPlayer model to include timing data for comprehensive analysis

```python
# Add to StratzPlayer class:
purchase_events: Optional[List[Dict[str, Any]]] = Field(alias="purchaseEvents", default=None)
ability_cast_report: Optional[List[Dict[str, Any]]] = Field(alias="abilityCastReport", default=None)

@property
def major_item_timings(self) -> List[str]:
    """Extract major item purchase timings for AI analysis."""
    if not self.purchase_events:
        return []

    major_items, _ = _analyze_stratz_purchase_events(self.purchase_events)
    return major_items

@property
def suspicious_purchase_patterns(self) -> List[str]:
    """Identify unusual purchase timing patterns."""
    if not self.purchase_events:
        return []

    _, suspicious = _analyze_stratz_purchase_events(self.purchase_events)
    return suspicious

@property
def ability_usage_anomalies(self) -> List[str]:
    """Identify unusual ability usage patterns."""
    if not self.ability_cast_report:
        return []

    return _analyze_ability_cast_patterns(self.ability_cast_report)
```

This extension allows the model to automatically provide Herald-specific insights about:
- **Item purchase timing**: Major items bought at unusual times
- **Support behavior**: Late ward purchases, role confusion
- **Ability usage**: Spam clicking, underused ultimates, never-used abilities

#### 4. Environment Configuration
**File**: `.env` (or environment setup)
**Change**: Ensure OpenAI API key available for production

```env
# Required for AI highlights generation
OPENAI_API_KEY=your_openai_api_key_here
```

### Success Criteria

#### Automated Verification:
- [ ] Enhanced Stratz models load correctly: `uv run python -c "from src.models.stratz import StratzPlayer, PurchaseEvent, AbilityCast; print('Enhanced models loaded')"`
- [ ] Enhanced context function works: `uv run python -c "from src.services.match_analysis import _build_match_context; print('Context function loaded')"`
- [ ] Function imports without errors: `uv run python -c "from src.services.match_analysis import generate_match_highlights; print('Function loaded')"`
- [ ] Mock API call with timing data succeeds: `uv run python -m pytest tests/services/test_match_analysis.py -v`
- [ ] Environment variable loaded: `uv run python -c "import os; print(bool(os.getenv('OPENAI_API_KEY')))"`
- [ ] Integration tests with enhanced data pass: `uv run python -m pytest tests/herald_reporter/ -v`

#### Manual Verification:
- [ ] Stratz GraphQL query returns purchaseEvents and abilityCastReport data
- [ ] AI highlights generate for test match within 5 seconds
- [ ] Highlights contain Herald-specific insights with timing information:
  - [ ] Raw purchase timing data provided to AI for analysis
  - [ ] Raw ability usage statistics with cast counts mapped to ability names
  - [ ] APM anomalies with specific minute ranges
  - [ ] Complete timing context allowing AI to discover patterns independently
- [ ] Graceful degradation when timing data unavailable (falls back to basic analysis)
- [ ] Graceful degradation when API fails (no highlights posted, no errors)
- [ ] Posting sequence: Summary → Teams → Highlights → Instructions
- [ ] Message formatting renders correctly in Discord with timing annotations


---

## Testing Strategy

### Unit Tests
- **Embed generation**: Test all formatting changes with mock data
- **LLM function**: Mock OpenAI responses to test error handling
- **Item display**: Validate complete inventory display formatting

### Integration Tests
- **End-to-end posting**: Full pipeline from match data to Discord posting
- **Error scenarios**: LLM failures, API timeouts, malformed data
- **Character limits**: Ensure all embeds stay within Discord constraints

### Manual Testing Steps
1. **Visual regression testing**: Compare before/after screenshots using test framework
2. **Real match validation**: Process actual Herald matches through development pipeline
3. **Performance validation**: Monitor response times and API costs during testing
4. **User experience testing**: Verify readability improvements on desktop Discord
5. **Error handling**: Test with malformed API responses and network failures

## Performance Considerations

### LLM Integration Cost Management
- **Expected monthly cost**: ~$8-20 for 500-1500 matches (increased due to richer context data)
  - Enhanced timing data increases context size by ~40% but provides much higher quality insights
  - Cost per analysis: $0.005-0.015 (vs $0.003-0.01 without timing data)
- **Context optimization**: Intelligent truncation of purchase logs for very long games (>90 minutes)
- **Graceful degradation**: System functions fully without LLM when API unavailable
- **Fallback levels**:
  1. Full analysis with timing data (preferred)
  2. Basic analysis without timing data (if Stratz query fails)
  3. No AI analysis (if OpenAI unavailable)
- **Rate limiting**: Built-in delays prevent API quota exhaustion

### Discord Rate Limiting
- **Current approach**: 1-second delays between embed posts
- **Enhanced sequence**: Additional 1-second delay before highlights message
- **Buffer strategy**: Monitor rate limit headers and implement backoff if needed

### Character Optimization
- **Current usage**: ~1,500 characters across all embeds (25% of single-embed limit)
- **Post-enhancement**: ~2,000-2,500 characters (40% of limit)
- **Safety margin**: Substantial room for future enhancements within Discord constraints

## Migration Notes

### Backward Compatibility
- **Existing slash commands**: No changes to `/ask` command functionality
- **API integration**: No changes to OpenDota or Stratz API usage patterns
- **Thread structure**: Maintains existing thread creation and naming conventions

### Deployment Strategy
- **Feature flags**: Environment variables to enable/disable new features during rollout
- **Gradual rollout**: Deploy phases incrementally with monitoring at each step
- **Rollback plan**: All changes are additive and can be reverted via configuration

### Data Migration
- **No database changes required**: All enhancements work with existing data models
- **Cache compatibility**: All changes work with existing cache entries

## References

- **Original research**: `thoughts/research/2025-09-15_comprehensive-research-compilation.md`
- **Current embed implementation**: `src/discord/embeds.py:23-127`
- **Herald discovery pipeline**: `src/herald_reporter.py:26-135`
- **Existing AI integration**: `src/commands/ask_command.py:124-166`
- **Testing framework**: `tests/live/test_discord_posting.py`
- **Character limit analysis**: Research compilation sections on Discord constraints
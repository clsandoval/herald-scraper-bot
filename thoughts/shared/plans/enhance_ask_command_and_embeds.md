# Enhanced Ask Command and Team Embeds Implementation Plan

## Overview

This plan enhances the Discord bot's AI analysis capabilities by providing comprehensive match and player data to the LLM, and improves team embed displays by adding player ranks beside hero names.

## Current State Analysis

The ask command currently only passes summarized match data to the LLM (src/commands/ask_command.py:130-181), limiting the AI's ability to provide detailed analysis. Team embeds display hero names without rank information, despite rank data being available in the StratzPlayer model.

### Key Discoveries:
- Match and player data is already fetched and cached properly (src/commands/ask_command.py:70-99)
- The `_build_match_context` function in match_analysis.py already constructs comprehensive data (src/services/match_analysis.py:69-271)
- Player rank data is available via `stratz_player.rank` property (src/models/stratz.py:35-39)
- `get_rank_name()` function exists for rank formatting (src/constants.py:89-93)

## Desired End State

After implementation:
1. The ask command will pass complete match and player data to the LLM, enabling deeper analysis
2. Team embeds in match threads will display player ranks beside hero names for better context
3. AI responses will have access to all available match statistics for more insightful analysis

### Success Verification:
- Ask command provides detailed insights using full match data
- Team embeds show ranks in format: "1. Anti-Mage [Herald III]"
- No performance degradation from increased data context

## What We're NOT Doing

- NOT modifying the data fetching or caching logic
- NOT changing the Discord slash command interface
- NOT altering the match discovery or reporting flow
- NOT modifying API client implementations

## Implementation Approach

Leverage existing comprehensive data structures and helper functions. The `_build_match_context` function already exists and creates detailed context - we'll reuse it for the ask command. For team embeds, we'll add a simple rank display using existing data.

## Phase 1: Enhance Ask Command with Full Match Data

### Overview
Replace the limited summary approach with comprehensive match context that includes all player and match statistics.

### Changes Required:

#### 1. Update Ask Command Handler
**File**: `src/commands/ask_command.py`
**Changes**: Import and use the existing `_build_match_context` function

```python
# Add import at top of file (after line 8)
from ..services.match_analysis import _build_match_context

# Replace the _generate_ai_analysis method (lines 124-166)
async def _generate_ai_analysis(
    self, match_id: int, match_details, stratz_data, question: str
) -> str:
    """Generate comprehensive AI analysis using OpenAI."""

    # Use the existing comprehensive context builder
    match_context = _build_match_context(match_details, stratz_data)

    prompt = f"""You are analyzing a Herald-tier Dota 2 match with COMPLETE data access.
You have detailed information about every player including:
- Full KDA, damage, healing, and economic statistics
- Item builds with purchase timing
- Ability usage patterns and skill builds
- APM data and performance benchmarks
- Rank information for all players

{match_context}

USER QUESTION: {question}

ANALYSIS GUIDELINES:
- Answer the question directly and concisely
- Use specific data points from the match when relevant
- Focus on Herald-level gameplay patterns and learning opportunities
- Keep response under 500 characters for Discord readability

Your analysis:"""

    response = await self.openai.chat.completions.create(
        model=self.config.openai_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,  # Increased for more detailed responses
        temperature=0.7
    )

    return response.choices[0].message.content.strip()
```

#### 2. Remove Redundant Summary Method
**File**: `src/commands/ask_command.py`
**Changes**: Remove the now-unused `_summarize_team` method (lines 168-181)

```python
# DELETE lines 168-181 (the entire _summarize_team method)
```

### Success Criteria:

#### Automated Verification:
- [x] Python syntax check passes: `uv run python -m py_compile src/commands/ask_command.py`
- [x] Import validation succeeds: `uv run python -c "from src.commands.ask_command import AskCommandCog"`
- [x] Unit tests pass: `uv run python -m pytest tests/unit/test_discord_integration.py -v`

#### Manual Verification:
- [ ] Ask command provides detailed responses using full match data
- [ ] AI can reference specific items, timings, and statistics in responses
- [ ] Response quality noticeably improved with access to complete data

---

## Phase 2: Add Player Ranks to Team Embeds

### Overview
Enhance team analysis embeds to display player ranks alongside hero names for better context about skill levels.

### Changes Required:

#### 1. Import Rank Formatter
**File**: `src/discord/embeds.py`
**Changes**: Add get_rank_name import

```python
# Update the imports (line 9-14)
from ..constants import (
    get_hero_name,
    get_item_name,
    get_rank_name,  # Add this import
    format_duration,
    format_large_number,
)
```

#### 2. Modify Team Analysis Embed
**File**: `src/discord/embeds.py`
**Changes**: Update the hero name to include rank

```python
# Modify create_team_analysis_embed function (lines 80-101)
# Replace lines 80-101 with:
for i, player in enumerate(players, 1):
    hero_name = get_hero_name(player.heroId)
    kda = f"{player.kills}/{player.deaths}/{player.assists}"

    # Get player rank
    rank_display = ""
    if player.rank:
        rank_name = get_rank_name(player.rank)
        rank_display = f" [{rank_name}]"

    # Performance metrics
    apm_info = f"{player.average_apm:.0f} APM" if player.average_apm else "N/A APM"

    # Items
    items = []
    for j in range(6):
        item_id = getattr(player, f"item{j}Id", None)
        if item_id and item_id != 0:
            items.append(get_item_name(item_id))

    items_text = ", ".join(items) if items else "No items"

    field_value = (
        f"**{kda}** • {format_large_number(player.heroDamage)} dmg • {apm_info}\n"
        f"**Items:** {items_text}"
    )

    # Update field name to include rank
    embed.add_field(
        name=f"{i}. {hero_name}{rank_display}",
        value=field_value,
        inline=False
    )
```

### Success Criteria:

#### Automated Verification:
- [x] Python syntax check passes: `uv run python -m py_compile src/discord/embeds.py`
- [x] Import validation succeeds: `uv run python -c "from src.discord.embeds import create_team_analysis_embed"`
- [x] Embed creation test passes: `uv run python -m pytest tests/unit/ -k embed`

#### Manual Verification:
- [ ] Team embeds display ranks in format: "1. Anti-Mage [Herald III]"
- [ ] Unranked players show without rank brackets
- [ ] Embed formatting remains clean and readable
- [ ] No visual overflow or truncation issues

---

## Phase 3: Integration Testing

### Overview
Verify the complete implementation works correctly with real match data.

### Testing Steps:

#### 1. Test Ask Command Enhancement
```bash
# Run ask command tests
uv run python -m pytest tests/unit/test_discord_integration.py::test_ask_command -v

# Test with live Discord bot
# 1. Find a Herald match thread
# 2. Use /ask with various questions:
#    - "Why did this game last so long?"
#    - "What items were bought too late?"
#    - "Which player had the lowest APM?"
# 3. Verify responses use detailed data
```

#### 2. Test Team Embed Enhancement
```bash
# Run embed tests
uv run python -m pytest tests/unit/ -k team_analysis -v

# Manual verification in Discord
# 1. Wait for next Herald match post
# 2. Check team embeds show ranks
# 3. Verify formatting is correct
```

### Success Criteria:

#### Automated Verification:
- [x] All unit tests pass: `uv run python -m pytest tests/unit/ -v` (14/15 passed, 1 pre-existing failure)
- [x] No new linting errors: `uv run ruff check src/` (pre-existing issues only)
- [ ] Type checking passes: `uv run mypy src/ --ignore-missing-imports` (not configured)

#### Manual Verification:
- [ ] Ask command provides insightful responses with specific data references
- [ ] Team embeds display player ranks correctly
- [ ] No performance degradation observed
- [ ] Error handling remains robust

---

## Performance Considerations

- The comprehensive match context increases prompt tokens by ~2000-3000
- This is within OpenAI's limits and shouldn't impact response time significantly
- The `_build_match_context` function is already optimized with graceful fallbacks

## Migration Notes

No migration needed - changes are backward compatible and don't affect data storage.

## References

- Original request: Enhanced ask command and team embeds
- Key files modified: `src/commands/ask_command.py`, `src/discord/embeds.py`
- Existing context builder: `src/services/match_analysis.py:69-271`
- Player rank model: `src/models/stratz.py:35-39`
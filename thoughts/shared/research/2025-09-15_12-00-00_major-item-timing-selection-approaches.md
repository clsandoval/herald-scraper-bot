---
date: 2025-09-15T12:00:00-05:00
researcher: Claude
git_commit: 3f01ce8fcf65aca9b0c8167fd6600cee59c25a76
branch: aesthetics-llm-calls
repository: herald-scraper-bot
topic: "Major Item Timing Selection Approaches - Including LLM-Based Selection"
tags: [research, codebase, discord, embeds, items, llm, ai-selection, dota2, herald]
status: complete
last_updated: 2025-09-15
last_updated_by: Claude
---

# Research: Major Item Timing Selection Approaches - Including LLM-Based Selection

**Date**: 2025-09-15T12:00:00-05:00
**Researcher**: Claude
**Git Commit**: 3f01ce8fcf65aca9b0c8167fd6600cee59c25a76
**Branch**: aesthetics-llm-calls
**Repository**: herald-scraper-bot

## Research Question
Compare different approaches to choosing which items to display in Discord embeds, including an LLM approach where the LLM chooses a set of 10 item timings to display

## Summary
Analysis of six distinct approaches to item selection for Discord embed display reveals trade-offs between simplicity, accuracy, and computational cost. The LLM-based approach offers the most sophisticated Herald-tier contextual analysis but introduces complexity and API costs. Traditional rule-based approaches provide reliable performance with predictable outputs. Hybrid approaches combining rule-based filtering with LLM refinement present the most practical solution for production deployment.

## Detailed Findings

### Current Implementation Analysis

#### Baseline System (`src/discord/embeds.py:89-101`)
- **Selection Method**: First 3 items from inventory slots (item0-item5)
- **No Intelligence**: Items displayed in slot order with no prioritization
- **Truncation**: `", ".join(items[:3]) + ("..." if len(items) > 3 else "")`
- **Performance**: O(1) - constant time, no API calls
- **Accuracy**: Low - ignores item importance, timing, and strategic value

## Comparison Framework: Six Selection Approaches

### Approach 1: Simple Cost Threshold (Rule-Based)

#### Implementation Strategy
```python
def select_major_items_by_cost(item_purchases, cost_threshold=2000):
    """Select items above cost threshold"""
    major_items = []
    for purchase in item_purchases:
        if get_item_cost(purchase.itemId) > cost_threshold:
            major_items.append({
                'name': get_item_name(purchase.itemId),
                'time': purchase.time,
                'cost': get_item_cost(purchase.itemId)
            })
    return sorted(major_items, key=lambda x: x['time'])[:10]
```

#### Pros & Cons
**✅ Advantages:**
- Simple implementation and testing
- Fast execution (O(n) where n = purchases)
- Predictable, consistent results
- No external API dependencies
- Easy to debug and maintain

**❌ Disadvantages:**
- Requires item cost database (currently missing from codebase)
- Ignores hero-specific item importance
- Cost doesn't always correlate with strategic value
- May miss important low-cost items (Blink Dagger = 2250 gold)
- No contextual analysis of game state

#### Technical Requirements
- **Missing Data**: Item cost database needs implementation
- **API Changes**: None required
- **Performance Impact**: Minimal

### Approach 2: Strategic Item Whitelist (Rule-Based)

#### Implementation Strategy
```python
STRATEGIC_ITEMS = {
    # Core Items
    1: "Blink Dagger",      # Always important for initiation
    214: "Black King Bar",  # BKB - crucial for survivability
    108: "Aghanim's Scepter", # Game-changing upgrades

    # Luxury Items
    218: "Linken's Sphere",  # Defensive luxury
    116: "Drums of Endurance", # Early-mid game impact

    # Situational but Herald-relevant
    102: "Vanguard",        # Herald players love tankiness
    237: "Boots of Travel",  # Late game mobility
}

def select_strategic_items(item_purchases):
    """Select from predefined strategic item list"""
    strategic_purchases = []
    for purchase in item_purchases:
        if purchase.itemId in STRATEGIC_ITEMS:
            strategic_purchases.append({
                'name': STRATEGIC_ITEMS[purchase.itemId],
                'time': purchase.time,
                'strategic_value': get_strategic_value(purchase.itemId)
            })
    return sorted(strategic_purchases, key=lambda x: x['time'])[:10]
```

#### Pros & Cons
**✅ Advantages:**
- Curated for Herald-tier relevance
- Focuses on impactful items regardless of cost
- Easy to maintain and update whitelist
- Fast execution with O(n) lookup
- Predictable results for testing

**❌ Disadvantages:**
- Static list requires manual curation
- May miss innovative or meta-changing builds
- Hero-agnostic (Blink useful for some heroes, not others)
- Requires game knowledge to maintain list
- Limited adaptability to patch changes

#### Technical Requirements
- **Data Structure**: Static item whitelist with strategic values
- **Maintenance**: Regular updates for meta changes
- **Testing**: Straightforward unit tests

### Approach 3: Usage Frequency Analysis (Data-Driven)

#### Implementation Strategy
```python
def select_by_usage_frequency(item_purchases, item_used_stats):
    """Select items by activation frequency during match"""
    usage_analysis = []

    for purchase in item_purchases:
        usage_count = get_usage_count(purchase.itemId, item_used_stats)
        activation_rate = usage_count / max(1, (match_duration - purchase.time) / 60)

        usage_analysis.append({
            'name': get_item_name(purchase.itemId),
            'time': purchase.time,
            'usage_count': usage_count,
            'activation_rate': activation_rate,
            'impact_score': calculate_impact_score(usage_count, activation_rate)
        })

    return sorted(usage_analysis, key=lambda x: x['impact_score'], reverse=True)[:10]

def calculate_impact_score(usage_count, activation_rate):
    """High usage + frequent activation = high impact"""
    return (usage_count * 0.6) + (activation_rate * 0.4)
```

#### Pros & Cons
**✅ Advantages:**
- Uses actual match data for decisions
- Identifies items that were actively used vs purchased and ignored
- Adapts automatically to player behavior
- No manual curation required
- Reveals player skill through item usage patterns

**❌ Disadvantages:**
- Passive items (stats-only) always rank low
- Usage data may be incomplete or inaccurate
- Complex impact scoring requires tuning
- May overweight activatable items
- Requires comprehensive item usage data

#### Technical Requirements
- **Available Data**: `itemUsed` stats already in Stratz API (`src/api/stratz.py:108-111`)
- **Algorithm Complexity**: Medium - requires impact scoring calibration

### Approach 4: Combat Integration Analysis (Event-Driven)

#### Implementation Strategy
```python
def select_by_combat_integration(item_purchases, kill_events, death_events):
    """Select items involved in combat outcomes"""
    combat_items = {}

    # Analyze kill events
    for event in kill_events:
        if event.byItem:
            combat_items[event.byItem] = combat_items.get(event.byItem, 0) + 2

    # Analyze death events (items that failed to save)
    for event in death_events:
        if event.byItem:
            combat_items[event.byItem] = combat_items.get(event.byItem, 0) + 1

    combat_analysis = []
    for purchase in item_purchases:
        combat_score = combat_items.get(purchase.itemId, 0)
        if combat_score > 0:  # Only items involved in combat
            combat_analysis.append({
                'name': get_item_name(purchase.itemId),
                'time': purchase.time,
                'combat_score': combat_score,
                'kills_secured': count_kills_by_item(purchase.itemId, kill_events),
                'deaths_while_owned': count_deaths_with_item(purchase.itemId, death_events)
            })

    return sorted(combat_analysis, key=lambda x: x['combat_score'], reverse=True)[:10]
```

#### Pros & Cons
**✅ Advantages:**
- Focuses on items that affected match outcomes
- Uses rich combat event data from Stratz API
- Identifies game-changing item moments
- Provides narrative context (this item secured kills)
- Automatically filters irrelevant items

**❌ Disadvantages:**
- May miss important passive/defensive items
- Complex event correlation logic
- Combat events might be incomplete in API data
- Requires careful event parsing and timing correlation
- Biased toward offensive items

#### Technical Requirements
- **Available Data**: Kill/death events in Stratz API (`src/api/stratz.py:120-135`)
- **Complexity**: High - requires event correlation and timing analysis

### Approach 5: Multi-Factor Hybrid (Rule + Data)

#### Implementation Strategy
```python
def select_hybrid_weighted(item_purchases, item_used_stats, kill_events, cost_data):
    """Combine multiple factors with weighted scoring"""
    item_scores = {}

    for purchase in item_purchases:
        item_id = purchase.itemId

        # Factor 1: Cost-based importance (0-40 points)
        cost_score = min(40, get_item_cost(item_id) / 100)

        # Factor 2: Strategic whitelist bonus (0-30 points)
        strategic_score = 30 if item_id in STRATEGIC_ITEMS else 0

        # Factor 3: Usage frequency (0-20 points)
        usage_count = get_usage_count(item_id, item_used_stats)
        usage_score = min(20, usage_count * 2)

        # Factor 4: Combat involvement (0-10 points)
        combat_score = min(10, count_combat_events(item_id, kill_events) * 5)

        total_score = cost_score + strategic_score + usage_score + combat_score

        item_scores[item_id] = {
            'name': get_item_name(item_id),
            'time': purchase.time,
            'total_score': total_score,
            'breakdown': {
                'cost': cost_score,
                'strategic': strategic_score,
                'usage': usage_score,
                'combat': combat_score
            }
        }

    return sorted(item_scores.values(), key=lambda x: x['total_score'], reverse=True)[:10]
```

#### Pros & Cons
**✅ Advantages:**
- Balances multiple decision factors
- Configurable weighting for different priorities
- Robust against single-factor failures
- Provides scoring breakdown for debugging
- Can be tuned based on user feedback

**❌ Disadvantages:**
- Complex implementation and testing
- Requires tuning of weight parameters
- May over-engineer simple problem
- Harder to explain selection logic to users
- Multiple data dependencies

#### Technical Requirements
- **Integration**: Combines all previous approaches
- **Maintenance**: Weight tuning and factor balancing

### Approach 6: LLM-Based Contextual Selection (AI-Driven)

#### Implementation Strategy
```python
async def select_items_via_llm(match_details, item_purchases, hero_data):
    """Use GPT-4o-mini to intelligently select 10 most important item timings"""

    # Preprocess item data for LLM
    item_context = []
    for purchase in item_purchases:
        item_context.append({
            'name': get_item_name(purchase.itemId),
            'time': format_duration(purchase.time),
            'hero': get_hero_name(purchase.heroId),
            'usage_count': get_usage_count(purchase.itemId, item_used_stats) or 0
        })

    prompt = f"""You are analyzing a Herald-tier Dota 2 match to select the 10 most important item timings for display in a Discord embed.

MATCH CONTEXT:
Duration: {match_details.duration_formatted}
Average Rank: Herald ({match_details.average_rank})
Total Kills: {match_details.total_kills}

HEROES IN MATCH:
{format_hero_list(hero_data)}

ALL ITEM PURCHASES:
{format_item_purchases(item_context)}

SELECTION CRITERIA:
1. Prioritize game-changing items (BKB, Blink, Aghs, etc.)
2. Focus on timing efficiency - unusually fast/slow major items
3. Consider Herald-tier relevance - items that significantly impact Herald games
4. Include build progression milestones (core→luxury transitions)
5. Highlight unusual or creative item choices
6. Factor in item usage frequency if available

SELECT EXACTLY 10 ITEMS with reasoning. Format as JSON:
{{
  "selections": [
    {{
      "hero": "Shadow Fiend",
      "item": "Blink Dagger",
      "time": "12:34",
      "reasoning": "Extremely fast Blink timing for Herald tier, likely game-changing initiation tool"
    }}
  ],
  "selection_strategy": "Brief explanation of overall selection approach"
}}

Response:"""

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)
```

#### Pros & Cons
**✅ Advantages:**
- **Contextual Intelligence**: Understands Herald-specific strategies and timing expectations
- **Hero-Aware Analysis**: Considers item appropriateness for specific heroes and team compositions
- **Meta Awareness**: Can factor in current patch meta and item effectiveness
- **Narrative Context**: Provides explanations for why items were selected
- **Adaptability**: Automatically adapts to new items, patches, and strategies
- **Multi-Factor Analysis**: Considers timing efficiency, usage patterns, and strategic value simultaneously
- **Creative Build Detection**: Identifies unusual or innovative item choices worth highlighting

**❌ Disadvantages:**
- **API Cost**: ~$0.002-0.005 per analysis (GPT-4o-mini pricing)
- **Latency**: 1-3 second response time vs instant rule-based selection
- **Reliability**: Potential for API failures, rate limits, or inconsistent responses
- **Complexity**: JSON parsing, error handling, prompt engineering maintenance
- **Token Limits**: Large matches may exceed context window (need truncation)
- **Debugging Difficulty**: AI decisions less predictable than rule-based logic

#### Technical Integration Pattern
Following existing LLM patterns in codebase (`src/commands/ask_command.py:124-166`):

```python
class ItemSelectionAnalyzer:
    def __init__(self, openai_client, config):
        self.openai_client = openai_client
        self.config = config

    async def select_items_for_display(self, match_data):
        if not self.config.has_openai:
            # Fallback to rule-based selection
            return select_major_items_by_cost(match_data.item_purchases)

        try:
            llm_selection = await self._llm_select_items(match_data)
            return self._format_for_embed(llm_selection)
        except Exception as e:
            logger.warning(f"LLM item selection failed: {e}, falling back to rules")
            return select_major_items_by_cost(match_data.item_purchases)
```

## Selection Approach Comparison Matrix

| Approach | Complexity | Cost | Accuracy | Maintainability | Performance |
|----------|------------|------|----------|----------------|-------------|
| **Cost Threshold** | Low | Free | Medium | High | Excellent |
| **Strategic Whitelist** | Low | Free | Medium-High | Medium | Excellent |
| **Usage Frequency** | Medium | Free | Medium | Medium | Good |
| **Combat Integration** | High | Free | Medium-High | Low | Good |
| **Multi-Factor Hybrid** | Very High | Free | High | Low | Good |
| **LLM Contextual** | Medium | ~$0.003/analysis | Very High | High | Fair |

## Discord Technical Constraints Analysis

### Character Limits for Item Display
Current field capacity analysis for 10-item display:

**Current Usage** (~100 chars per player):
```
**KDA:** 8/2/12
**Damage:** 45,231
**APM:** 180 APM
**Items:** Power Treads...
```

**With 10 Major Items** (~400-500 chars per player):
```
**KDA:** 8/2/12
**Damage:** 45,231
**APM:** 180 APM
**Core:** Treads(5:21) Blink(12:34) BKB(18:45)
**Luxury:** Aghs(25:12) Linkens(32:45)
**Situational:** Lotus(28:30) Force(15:20) Dust(22:10) Gem(35:45) TP(40:12)
```

**Capacity Analysis**:
- Discord limit: 1,024 characters per field
- 10-item display: ~500 characters
- **✅ Feasible**: 50% capacity usage with room for expansion

### Mobile Display Optimization
For 10-item display with line breaks:
```
**Major Items:**
Core: Blink(12:34) BKB(18:45) Aghs(25:12)
Luxury: Linkens(32:45) Lotus(28:30)
Support: Force(15:20) Dust(22:10) Gem(35:45) TP(40:12) Ward(3:45)
```

## Implementation Recommendations

### Recommended Approach: LLM + Rule-Based Hybrid

**Phase 1: Rule-Based Foundation (Immediate)**
```python
# Fallback system using strategic whitelist + cost threshold
def select_items_fallback(item_purchases):
    # Strategic items get priority
    strategic = [p for p in item_purchases if p.itemId in STRATEGIC_ITEMS]
    # Fill remaining slots with high-cost items
    expensive = [p for p in item_purchases if get_item_cost(p.itemId) > 2000]
    return (strategic + expensive)[:10]
```

**Phase 2: LLM Enhancement (Advanced)**
```python
# LLM selection with graceful degradation
async def select_items_intelligent(match_data):
    if openai_available():
        try:
            return await llm_select_items(match_data)
        except Exception:
            logger.info("LLM selection failed, using rule-based fallback")
    return select_items_fallback(match_data.item_purchases)
```

**Phase 3: User Preference Configuration**
```python
# src/config.py additions
class Config:
    item_selection_method: str = Field(
        default="hybrid",
        description="Item selection: 'simple', 'strategic', 'hybrid', 'llm'"
    )
    max_items_display: int = Field(
        default=10,
        description="Maximum items to display per player"
    )
```

### Cost Analysis for LLM Approach

**GPT-4o-mini Pricing** (as of 2025):
- Input: $0.150 per 1M tokens
- Output: $0.600 per 1M tokens

**Per-Match Analysis**:
- Input tokens: ~800 (match context + item list)
- Output tokens: ~200 (JSON response)
- **Cost per analysis**: ~$0.0025

**Monthly Usage** (100 Herald matches):
- Total cost: ~$0.25/month
- **Extremely affordable** for the intelligence gained

### Testing Strategy

**Unit Tests for Each Approach**:
```python
def test_cost_threshold_selection():
    assert len(select_by_cost(sample_purchases, 2000)) <= 10
    assert all(item.cost > 2000 for item in result)

def test_llm_selection_fallback():
    with mock_openai_failure():
        result = select_items_intelligent(sample_data)
        assert len(result) <= 10  # Fallback works

def test_discord_character_limits():
    result = format_items_for_embed(ten_item_selection)
    assert len(result) < 1024  # Fits in Discord field
```

**Integration Tests**:
- Live API testing with real match data
- Discord posting verification
- Performance benchmarking across approaches

## Code References

### Implementation Files
- `src/discord/embeds.py:89-101` - Current item display logic to extend
- `src/constants.py:75-79` - Item name resolution system
- `src/api/stratz.py:108-117` - Item purchase and usage data
- `src/commands/ask_command.py:124-166` - LLM integration patterns

### Data Sources
- `src/data/item_ids.json:1-71` - Current item mapping (70 items)
- `truths/api/stratz_graphql_response.json` - Sample item purchase data
- `src/api/stratz.py:154-157` - Purchase event structure

### Configuration and Testing
- `src/config.py:29-32` - OpenAI configuration patterns
- `tests/live/test_discord_posting.py` - Live embed testing infrastructure
- `tests/conftest.py:169-178` - OpenAI mocking for tests

## Historical Context (from thoughts/)

### Existing Research Foundation
- **Primary Reference**: `thoughts/shared/research/2025-09-15_05-11-27_message-aesthetics-improvement-analysis.md` - Contains user preference research establishing item timing display priority
- **Technical Foundation**: `thoughts/shared/research/2025-09-12_12-00-00_discord-embed-aesthetics-overhaul.md` - Discord embed optimization strategies
- **Architecture Context**: `thoughts/shared/plans/herald-bot-unified-implementation.md` - Herald-specific filtering and selection patterns

### User Preference Decisions (Established)
- **Information Priority**: KDA, Total Hero Damage, APM, **Item Build with progression timings**
- **Display Preference**: Consolidated presentation (one embed per team)
- **Item Format**: Progression indicators with timing (`item_1→item_2→etc`)
- **Mobile Optimization**: Not a primary concern

## Open Questions

### Configuration Decisions
1. **Default Selection Method**: Should LLM be default or opt-in?
2. **Item Count**: Is 10 items optimal or should this be configurable?
3. **Cost Threshold**: If using cost-based fallback, what gold value threshold?
4. **Update Frequency**: How often should strategic item whitelist be updated?

### Technical Considerations
1. **Rate Limiting**: How to handle OpenAI API rate limits during high usage?
2. **Cache Strategy**: Should LLM selections be cached to reduce API calls?
3. **Error Recovery**: What's the best fallback hierarchy when systems fail?
4. **A/B Testing**: How to measure effectiveness of different approaches?

## Next Steps

### Implementation Priority
1. **Phase 1**: Implement cost threshold + strategic whitelist hybrid (1-2 days)
2. **Phase 2**: Add LLM selection with fallback (2-3 days)
3. **Phase 3**: User configuration and A/B testing (1-2 days)
4. **Phase 4**: Performance optimization and caching (1 day)

### Data Requirements
1. **Item Cost Database**: Extend `src/data/item_ids.json` with cost data
2. **Strategic Item Curation**: Herald-specific important items list
3. **Performance Baseline**: Current selection speed benchmarking

### Testing Requirements
1. **Unit Tests**: All selection algorithms with edge cases
2. **Integration Tests**: Discord posting with 10-item displays
3. **Performance Tests**: LLM response time and cost monitoring
4. **User Acceptance**: Discord embed readability testing

---

**Note**: This research extends the existing aesthetic improvement analysis in `thoughts/shared/research/2025-09-15_05-11-27_message-aesthetics-improvement-analysis.md` with detailed comparison of item selection approaches, establishing technical feasibility and implementation roadmap for LLM-enhanced item timing display.
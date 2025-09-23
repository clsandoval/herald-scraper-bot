"""AI-powered match analysis functions for generating Herald match highlights."""

import os
from typing import Optional
from openai import AsyncOpenAI
from ..models.stratz import StratzMatchData
from ..models.opendota import OpenDotaMatchDetail
from ..constants import (
    get_hero_name,
    get_item_name,
    get_ability_name,
    get_rank_name,
    format_duration,
    format_large_number,
)


async def generate_match_highlights(
    match_details: OpenDotaMatchDetail, stratz_data: StratzMatchData
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
    - Extremely late or early major item acquisitions

    **Ability & Behavioral Analysis:**
    - Spam clicking patterns (300+ casts of basic abilities)

    **Herald-Specific Patterns:**
    - Performance benchmark extremes (hero damage above 200k, etc.)
    - Late-game item builds that make no sense for game state

    Format as markdown bullet points (Maximum of 10). Include specific timings and statistics when available.
    Start with: "## 📝 Herald Match Insights (With Precise Timing Data)"

    Use the comprehensive timing data to create insights that go beyond surface-level observations.
    Here is a great example for the format:

    • “Hard-support” Viper went full carry: Silver Edge → Butterfly → Skadi → Deso, zero boots for 82 minutes, 24-18-35 – out-farm­ing both real carries.  
    • Hoodwink bought 105 items, hit Dagon 5 at 79 min, and somehow “used ward dispenser” 87 times for only 73 wards – spammed the empty box harder than her spells.  
    • Magnus bought Blink, then Harpoon, then Overwhelming Blink and kept all three; had multiple 0–1 APM minutes (clearly alt-tabbed), yet still ended 11-22-26.  
    • Necro deleted people just by existing: 32 kills, 22 of them from Heartstopper Aura/Radiance burn – literal walk-by murders.  
    • Axe mashed Phase Boots 185 times, built Veil of Discord(!) and Aghs, finished 31-19-29 and solo-culled half of Radiant.  
    • Invoker’s level-15 skill shows up as “dota_base_ability”; picked it anyway, then chained Refresher + Octarine + double Boots of Travel because why not.  
    • Techies support pivoted into Mask of Madness + Mjollnir + Bloodstone, died 23 times, but still found time to kill Radiant courier and himself—often simultaneously.  
    • Pudge managed 5-26-34, skipped Blink until 59 min, bought Overwhelming Blink at 82 min – perfect Herald timing.  
    • Radiant ran a four-core lineup (Viper, Necro, Magnus, Tinker) yet let an 84-minute clown fiesta drag on with 114 total deaths on their side alone.  
    • Highlight throw: Dire up ~15 k, Axe dives fountain with double BKB+Refresher shard, feeds, chain-feeds follow; game flips and crawls to 84-minute finish.

    The entire output should be less than 1500 characters
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
            ],
        )

        return response.choices[0].message.content

    except Exception:
        # Graceful degradation
        return None


def _build_match_context(
    match_details: OpenDotaMatchDetail, stratz_data: StratzMatchData
) -> str:
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
        "",
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
        context_parts.append(
            f"  Level: {stratz_player.level or opendota_player.get('level', 'N/A')}"
        )
        context_parts.append(f"  Position: {stratz_player.position or 'Unknown'}")

        # Damage and performance
        context_parts.append(
            f"  Hero Damage: {format_large_number(stratz_player.heroDamage)}"
        )
        if "hero_healing" in opendota_player:
            context_parts.append(
                f"  Hero Healing: {format_large_number(opendota_player['hero_healing'])}"
            )
        if "tower_damage" in opendota_player:
            context_parts.append(
                f"  Tower Damage: {format_large_number(opendota_player['tower_damage'])}"
            )

        # Economic stats from OpenDota
        if "gold_per_min" in opendota_player:
            context_parts.append(f"  GPM: {opendota_player['gold_per_min']}")
        if "xp_per_min" in opendota_player:
            context_parts.append(f"  XPM: {opendota_player['xp_per_min']}")
        if "last_hits" in opendota_player:
            context_parts.append(f"  Last Hits: {opendota_player['last_hits']}")
        if "denies" in opendota_player:
            context_parts.append(f"  Denies: {opendota_player['denies']}")
        if "net_worth" in opendota_player:
            context_parts.append(
                f"  Net Worth: {format_large_number(opendota_player['net_worth'])}"
            )

        # APM data from Stratz
        if stratz_player.average_apm:
            apm_data = stratz_player.actions_per_minute
            min_apm = min(apm_data) if apm_data else 0
            max_apm = max(apm_data) if apm_data else 0
            context_parts.append(
                f"  APM: {stratz_player.average_apm:.0f} avg (range: {min_apm}-{max_apm})"
            )

            # APM anomalies detection
            if apm_data:
                zero_minutes = sum(1 for apm in apm_data if apm == 0)
                if zero_minutes > 0:
                    context_parts.append(
                        f"  ⚠️ APM Anomaly: {zero_minutes} minutes with 0 APM"
                    )
                if max_apm > 300:
                    context_parts.append(
                        f"  ⚠️ APM Anomaly: Peak of {max_apm} APM (unusually high)"
                    )

        # Rank information
        if stratz_player.rank:
            rank_name = get_rank_name(stratz_player.rank)
            context_parts.append(f"  Rank: {rank_name} ({stratz_player.rank})")
        elif "rank_tier" in opendota_player and opendota_player["rank_tier"]:
            rank_name = get_rank_name(opendota_player["rank_tier"])
            context_parts.append(
                f"  Rank: {rank_name} ({opendota_player['rank_tier']})"
            )

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
        if "item_neutral" in opendota_player and opendota_player["item_neutral"]:
            neutral_items.append(get_item_name(opendota_player["item_neutral"]))
        if "item_neutral2" in opendota_player and opendota_player["item_neutral2"]:
            neutral_items.append(get_item_name(opendota_player["item_neutral2"]))

        context_parts.append(
            f"  Final Items: {', '.join(items) if items else 'No items'}"
        )
        if backpack_items:
            context_parts.append(f"  Backpack: {', '.join(backpack_items)}")
        if neutral_items:
            context_parts.append(f"  Neutral Items: {', '.join(neutral_items)}")

        # Purchase timing data from Stratz
        if hasattr(stratz_player, "purchase_events") and stratz_player.purchase_events:
            # Raw purchase timing data available for AI analysis
            purchase_build = []
            for p in stratz_player.purchase_events:
                item_id = p.get("itemId")
                time_sec = p.get("time", 0)
                if item_id:
                    item_name = get_item_name(item_id)
                    if time_sec > 0:
                        minutes = time_sec // 60
                        purchase_build.append(f"{item_name} @{minutes}m")
                    else:
                        purchase_build.append(item_name)

            if purchase_build:
                context_parts.append(
                    f"  Item Purchase Timeline: {', '.join(purchase_build)}"
                )

        # Special items/upgrades from OpenDota
        upgrades = []
        if opendota_player.get("aghanims_scepter"):
            upgrades.append("Aghanim's Scepter")
        if opendota_player.get("aghanims_shard"):
            upgrades.append("Aghanim's Shard")
        if opendota_player.get("moonshard"):
            upgrades.append("Consumed Moonshard")
        if upgrades:
            context_parts.append(f"  Special Upgrades: {', '.join(upgrades)}")

        # Ability build from OpenDota
        if "ability_upgrades_arr" in opendota_player:
            ability_upgrades = opendota_player["ability_upgrades_arr"]
            if ability_upgrades:
                ability_names = [
                    get_ability_name(ability_id) for ability_id in ability_upgrades
                ]
                context_parts.append(f"  Skill Build {' → '.join(ability_names)}")

        # Ability usage data from Stratz (if available)
        # Note: This requires accessing raw Stratz GraphQL response data
        # The current StratzPlayer model doesn't include abilityCastReport
        if (
            hasattr(stratz_player, "ability_cast_report")
            and stratz_player.ability_cast_report
        ):
            # Raw ability usage data for AI analysis
            ability_usage = []
            for ability_report in stratz_player.ability_cast_report:
                ability_id = ability_report.get("abilityId")
                cast_count = ability_report.get("count", 0)
                ability_name = get_ability_name(ability_id)
                ability_usage.append(f"{ability_name}: {cast_count} casts")

            if ability_usage:
                context_parts.append(f"  Ability Usage: {', '.join(ability_usage)}")

        # Kill events data from Stratz
        if hasattr(stratz_player, "kill_events") and stratz_player.kill_events:
            kill_count = len(stratz_player.kill_events)
            # Extract interesting kill patterns
            first_blood = any(k.get("isFirstBlood") for k in stratz_player.kill_events)
            multi_kills = []
            for event in stratz_player.kill_events:
                if event.get("isUltraKill"):
                    multi_kills.append("Ultra Kill")
                elif event.get("isTripleKill"):
                    multi_kills.append("Triple Kill")
                elif event.get("isDoubleKill"):
                    multi_kills.append("Double Kill")

            context_parts.append(f"  Kill Events: {kill_count} total kills")
            if first_blood:
                context_parts.append(f"    - First Blood")
            if multi_kills:
                context_parts.append(f"    - Multi-kills: {', '.join(set(multi_kills))}")

        # Death events data from Stratz
        if hasattr(stratz_player, "death_events") and stratz_player.death_events:
            death_count = len(stratz_player.death_events)
            # Extract interesting death patterns
            death_timings = []
            for event in stratz_player.death_events:
                if "time" in event:
                    death_timings.append(event["time"])

            context_parts.append(f"  Death Events: {death_count} total deaths")
            if death_timings:
                # Check for feeding patterns (deaths within 60 seconds of each other)
                rapid_deaths = 0
                for i in range(1, len(death_timings)):
                    if death_timings[i] - death_timings[i-1] < 60:
                        rapid_deaths += 1
                if rapid_deaths > 2:
                    context_parts.append(f"    - Rapid deaths detected: {rapid_deaths} deaths within 60s of previous death")

        # Player behavior indicators
        if "leaver_status" in opendota_player and opendota_player["leaver_status"] != 0:
            context_parts.append(
                f"  ⚠️ Leaver Status: {opendota_player['leaver_status']}"
            )

        context_parts.append("")  # Separator between players

    # Match-wide statistics
    context_parts.append("=== MATCH STATISTICS ===")
    context_parts.append(
        f"Average Match APM: {stratz_data.average_apm:.0f}"
        if stratz_data.average_apm
        else "Average APM: N/A"
    )
    context_parts.append(f"All Players Herald Rank: {stratz_data.all_players_herald}")

    # Team totals
    radiant_kills = sum(p.kills for p in stratz_data.radiant_players)
    dire_kills = sum(p.kills for p in stratz_data.dire_players)
    radiant_damage = sum(p.heroDamage for p in stratz_data.radiant_players)
    dire_damage = sum(p.heroDamage for p in stratz_data.dire_players)

    context_parts.append(f"Team Kills - Radiant: {radiant_kills}, Dire: {dire_kills}")
    context_parts.append(
        f"Team Damage - Radiant: {format_large_number(radiant_damage)}, Dire: {format_large_number(dire_damage)}"
    )

    return "\n".join(context_parts)

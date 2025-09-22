"""Unified Discord embed system for Herald match presentation."""

import discord
from datetime import datetime, timezone
from typing import List, Optional

from ..models.opendota import OpenDotaMatchDetail
from ..models.stratz import StratzMatchData, StratzPlayer
from ..constants import (
    get_hero_name,
    get_item_name,
    get_rank_name,
    format_duration,
    format_large_number,
)

# Team colors
RADIANT_COLOR = 0x00FF00  # Green
DIRE_COLOR = 0xFF0000  # Red
HERALD_COLOR = 0xFFD700  # Gold for Herald-specific content


def create_match_summary_embed(
    match_details: OpenDotaMatchDetail, stratz_data: StratzMatchData
) -> discord.Embed:
    """Create comprehensive match summary embed combining OpenDota and Stratz data."""
    embed = discord.Embed(
        title="🏆 Herald Match Analysis",
        description=f"**Match ID:** [{match_details.match_id}](https://stratz.com/matches/{match_details.match_id})",
        color=HERALD_COLOR,
        url=f"https://stratz.com/matches/{match_details.match_id}",
    )

    # Match metadata from OpenDota
    match_date = datetime.fromtimestamp(match_details.start_time, tz=timezone.utc)
    duration_str = format_duration(match_details.duration)

    embed.add_field(
        name="📅 Date", value=match_date.strftime("%Y-%m-%d %H:%M UTC"), inline=True
    )
    embed.add_field(name="⏱️ Duration", value=duration_str, inline=True)

    # Analytics from Stratz data
    total_kills = stratz_data.total_kills
    kill_density = (
        round(total_kills / (match_details.duration / 60), 2)
        if match_details.duration > 0
        else 0
    )

    embed.add_field(
        name="⚔️ Kill Density", value=f"{kill_density} kills/min", inline=True
    )
    embed.add_field(name="💀 Total Kills", value=str(total_kills), inline=True)

    embed.timestamp = match_date
    embed.set_footer(
        text="Use /ask in this thread for detailed analysis",
        icon_url="https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/icons/hero_strength.png",
    )

    return embed


def create_team_analysis_embed(
    players: List[StratzPlayer], is_radiant: bool, player_wl_data: dict = None
) -> discord.Embed:
    """Create detailed team analysis embed with player breakdowns."""
    team_name = "Radiant" if is_radiant else "Dire"
    color = RADIANT_COLOR if is_radiant else DIRE_COLOR
    emoji = "🌅" if is_radiant else "🌙"

    embed = discord.Embed(title=f"{emoji} {team_name} Team Analysis", color=color)

    # Team-level statistics
    team_kills = sum(p.kills for p in players)

    embed.description = f"**Team Kills:** {team_kills}"

    # Individual player analysis
    for i, player in enumerate(players, 1):
        hero_name = get_hero_name(player.heroId)
        kda = f"{player.kills}/{player.deaths}/{player.assists}"

        # Performance metrics
        apm_info = f"{player.average_apm:.0f} APM" if player.average_apm else "N/A APM"

        # Win/Loss data
        wl_text = "**W/L:** N/A"
        if player_wl_data and player.heroId in player_wl_data:
            wins, losses = player_wl_data[player.heroId]
            total_games = wins + losses
            if total_games > 0:
                win_rate = (wins / total_games) * 100
                wl_text = f"**W/L:** {wins}/{losses} ({win_rate:.1f}%)"
            else:
                wl_text = f"**W/L:** {wins}/{losses}"

        # Items
        items = []
        for j in range(6):
            item_id = getattr(player, f"item{j}Id", None)
            if item_id and item_id != 0:
                items.append(get_item_name(item_id))

        items_text = ", ".join(items[:3]) + ("..." if len(items) > 3 else "")

        field_value = (
            f"**KDA:** {kda}\n"
            f"**Damage:** {format_large_number(player.heroDamage)}\n"
            f"{wl_text}\n"
            f"**APM:** {apm_info}\n"
            f"**Items:** {items_text}"
        )

        embed.add_field(name=f"{i}. {hero_name}", value=field_value, inline=True)

    return embed


def create_ai_response_embed(
    question: str, response: str, match_id: int
) -> discord.Embed:
    """Create embed for AI-powered match analysis responses."""
    embed = discord.Embed(
        title="🤖 AI Match Analysis",
        description=f"**Question:** {question}",
        color=HERALD_COLOR,
    )

    # Truncate long responses
    if len(response) > 800:
        response = response[:800] + "\n\n*[Response truncated for Discord limits]*"

    embed.add_field(name="Analysis", value=response, inline=False)
    embed.set_footer(text=f"Analysis for Match {match_id} | Powered by GPT-4o-mini")

    return embed

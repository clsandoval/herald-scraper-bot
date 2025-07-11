import discord
from discord.ext import commands
import asyncio
import logging
import time
import os
from datetime import datetime
from dotenv import load_dotenv
from functions import *

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Get Discord bot token from environment
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = (
    int(os.getenv("DISCORD_CHANNEL_ID")) if os.getenv("DISCORD_CHANNEL_ID") else None
)

if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

if not DISCORD_CHANNEL_ID:
    raise ValueError("DISCORD_CHANNEL_ID environment variable is required")


def create_match_embed(match_id, date, duration, kill_density):
    """Create a Discord embed for match summary"""
    embed = discord.Embed(
        title=f"🏆 Herald Match Analysis",
        description=f"Match ID: {match_id}",
        color=0x00FF00,
        url=f"https://stratz.com/matches/{match_id}",
    )

    embed.add_field(name="📅 Date", value=date, inline=True)
    embed.add_field(
        name="⏱️ Duration", value=f"{duration//60}m {duration%60}s", inline=True
    )
    embed.add_field(name="⚔️ Kill Density", value=f"{kill_density:.2f}", inline=True)

    embed.set_footer(
        text="Herald Scraper Bot",
        icon_url="https://cdn.discordapp.com/attachments/123456789/dota2_icon.png",
    )
    embed.timestamp = datetime.utcnow()

    return embed


def create_player_embed(stratz_response):
    """Create Discord embeds for player summaries"""

    def get_hero_name(hero_id):
        return HEROES.get(hero_id, f"Unknown Hero {hero_id}")

    def get_item_name(item_id):
        if item_id is None:
            return "Empty"
        return ITEMS.get(item_id, f"Unknown Item {item_id}")

    def format_herald_rank(rank):
        if rank is None:
            return "Unranked"
        if 11 <= rank <= 15:
            herald_level = rank - 10
            return f"Herald {herald_level}"
        else:
            return f"Rank {rank}"

    match = stratz_response["data"]["match"]

    # Teams
    radiant_players = [p for p in match["players"] if p["isRadiant"]]
    dire_players = [p for p in match["players"] if not p["isRadiant"]]

    embeds = []

    def create_team_embed(players, team_name, color):
        embed = discord.Embed(title=f"🛡️ {team_name} Team", color=color)

        for i, player in enumerate(players):
            hero_name = get_hero_name(player["heroId"])
            kda = f"{player['kills']}/{player['deaths']}/{player['assists']}"

            # Rank
            rank = None
            if player["steamAccount"] and player["steamAccount"]["seasonRank"]:
                rank = player["steamAccount"]["seasonRank"]
            rank_str = format_herald_rank(rank)

            # Items (shortened for embed)
            items = [
                get_item_name(player.get("item0Id")),
                get_item_name(player.get("item1Id")),
                get_item_name(player.get("item2Id")),
                get_item_name(player.get("item3Id")),
                get_item_name(player.get("item4Id")),
                get_item_name(player.get("item5Id")),
            ]
            items_str = " | ".join([item for item in items if item != "Empty"])

            # Average APM
            avg_apm = "N/A"
            if "stats" in player and "actionsPerMinute" in player["stats"]:
                apm_values = player["stats"]["actionsPerMinute"]
                if apm_values:
                    avg_apm = f"{sum(apm_values) / len(apm_values):.1f}"

            # Dota Plus Level
            dota_plus_level = "None"
            if player["dotaPlus"] and player["dotaPlus"]["level"]:
                dota_plus_level = str(player["dotaPlus"]["level"])

            field_value = f"**KDA:** {kda} | **Rank:** {rank_str} | **APM:** {avg_apm} | **Dota+:** {dota_plus_level}"
            if items_str:
                field_value += f"\n**Items:** {items_str}"

            embed.add_field(name=f"{hero_name}", value=field_value, inline=False)

        return embed

    # Create embeds for both teams
    radiant_embed = create_team_embed(radiant_players, "RADIANT", 0x00FF00)
    dire_embed = create_team_embed(dire_players, "DIRE", 0xFF0000)

    return [radiant_embed, dire_embed]


async def send_herald_report():
    """Main function to scrape and send herald reports"""
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID {DISCORD_CHANNEL_ID}")
            return

        logger.info("Start Herald Match Scraping")
        json_data = query(days_back=1)
        logger.info("Opendota Data Pulled")

        matches = [i["match_id"] for i in json_data["rows"]]
        durations = [i["duration"] for i in json_data["rows"]]
        dates = [
            datetime.utcfromtimestamp(int(i["start_time"])).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            for i in json_data["rows"]
        ]

        logger.info(f"Found {len(matches)} matches to process")

        for match, duration, date in zip(matches, durations, dates):
            try:
                match_data = get_match_data_nostratz(match)
                max_hero_damage, hero_id = get_max_hero_damage(match_data)
                hero_name = HERO_ID_TO_NAME.get(hero_id, "Unknown")
                kill_density = ret_kill_density_nostratz(match_data)
                players = get_match_data_nostratz(match)["players"]

                # Get stratz response for enhanced analysis
                stratz_response = query_stratz(match)

                leaver = 0
                for player in players:
                    if player["leaver_status"] != 0:
                        leaver = 1

                if leaver == 0:
                    # get granular list of player data from stratz
                    stratz_players_data = stratz_info(match)["data"]["match"]["players"]
                    if check_for_guardian(stratz_players_data):
                        continue

                    # Create and send match summary embed
                    match_embed = create_match_embed(
                        match, date, duration, kill_density
                    )
                    await channel.send(embed=match_embed)

                    # Create and send player embeds
                    player_embeds = create_player_embed(stratz_response)
                    for embed in player_embeds:
                        await channel.send(embed=embed)

                    # Get and send LLM summary as markdown
                    formatted_output = format_match_data(stratz_response)
                    llm_summary = get_llm_summary(formatted_output)

                    # Send LLM summary with markdown formatting
                    await channel.send(
                        f"## 📝 Match Analysis (Exact Timings might not be accurate due to API error)\n```\n{llm_summary}\n```"
                    )

                    logger.info(f"Processed match {match}")

                    # Wait between messages to avoid rate limiting
                    await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error processing match {match}: {str(e)}")
                continue

        logger.info("Scrape complete")

    except Exception as e:
        logger.error(f"Fatal error in send_herald_report: {str(e)}")
        raise


@bot.event
async def on_ready():
    """Called when the bot is ready - automatically run herald report and close"""
    logger.info(f"{bot.user} has connected to Discord!")
    logger.info(f"Bot is in {len(bot.guilds)} guilds")

    try:
        # Run the herald report automatically
        await send_herald_report()
        logger.info("Herald report completed successfully")
    except Exception as e:
        logger.error(f"Error running herald report: {str(e)}")
    finally:
        # Close the bot after completion
        logger.info("Closing Discord bot...")
        await bot.close()


async def main():
    """Main function to run the bot"""
    try:
        await bot.start(DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {str(e)}")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())

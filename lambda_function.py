# %%
from dotenv import load_dotenv

load_dotenv()
from functions import *
import logging, time
import telebot
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

tb = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))


def main():
    """Main function to run the herald match scraper"""
    try:
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

                # llm informed
                stratz_response = query_stratz(match)
                formatted_output = format_match_data(stratz_response)
                llm_summary = get_llm_summary(formatted_output)

                leaver = 0
                for player in players:
                    if player["leaver_status"] != 0:
                        leaver = 1

                if leaver == 0:
                    # get granular list of player data from stratz
                    stratz_players_data = stratz_info(match)["data"]["match"]["players"]
                    if check_for_guardian(stratz_players_data):
                        continue

                    match_summary = f"""
--------------------------------------
| Match ID   : {match}
| Date       : {date}
| Duration   : {duration}
| KD         : {kill_density}
| URL        : stratz.com/matches/{match}
--------------------------------------
"""
                    radiant, dire = create_heroes_string(stratz_players_data)
                    send_message(f"```{match_summary}```")
                    # send_message(f"```{radiant}```")
                    # send_message(f"```{dire}```")
                    send_message(f"```{llm_summary}```")

                    logger.info(f"Processed match {match}")

                time.sleep(1)

            except Exception as e:
                logger.error(f"Error processing match {match}: {str(e)}")
                continue

        logger.info("Scrape complete")

    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        raise


if __name__ == "__main__":
    main()

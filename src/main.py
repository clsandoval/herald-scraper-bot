"""Main entry point for the Herald Discord Bot."""

import asyncio
import logging
import sys
from dotenv import load_dotenv

from .config import Config
from .bot import UnifiedHeraldBot
from .health_server import HealthServer


def setup_logging():
    """Configure logging for the bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/herald_bot.log", encoding="utf-8"),
        ],
    )


async def main():
    """Main application entry point."""
    # Load environment variables
    load_dotenv()

    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config = Config.from_env()
        config.validate_required()
        logger.info("Configuration loaded successfully")

        # Check for dry run
        if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
            logger.info("Dry run mode - validating configuration only")
            logger.info(
                f"Discord Bot Token: {'***' + config.discord_bot_token[-4:] if config.discord_bot_token else 'Not set'}"
            )
            logger.info(f"Discord Test Channel ID: {config.discord_test_channel_id}")
            logger.info(
                f"OpenDota API Key: {'***' + config.opendota_api_key[-4:] if config.opendota_api_key else 'Not set'}"
            )
            logger.info(
                f"Stratz API Token: {'***' + config.stratz_api_token[-4:] if config.stratz_api_token else 'Not set'}"
            )
            logger.info(f"OpenAI Available: {config.has_openai}")
            logger.info("Dry run completed - configuration is valid")
            return

        # Create and run bot
        bot = UnifiedHeraldBot(config)

        # Create health server for monitoring
        health_server = HealthServer(bot)

        async with bot:
            # Start health server
            await health_server.start()

            try:
                logger.info("Starting Herald Discord Bot...")
                await bot.start(config.discord_bot_token)
            finally:
                # Stop health server on shutdown
                await health_server.stop()

    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

"""Interactive ask command for AI-powered Herald match analysis."""

import discord
from discord.ext import commands
from discord import app_commands
import re
import asyncio
import logging
from typing import Optional, List

from ..api.opendota import OpenDotaClient
from ..services.match_analysis import _build_match_context
from ..api.stratz import StratzClient
from ..cache.match_cache import UnifiedMatchCache
from ..constants import get_hero_name, get_rank_name
from ..config import Config

logger = logging.getLogger(__name__)


class AskCommandCog(commands.Cog):
    """Interactive AI analysis commands for Herald matches."""

    def __init__(
        self, bot: commands.Bot, config: Config, cache: UnifiedMatchCache, openai_client
    ):
        self.bot = bot
        self.config = config
        self.cache = cache
        self.openai = openai_client
        self.opendota_client = OpenDotaClient(config)
        self.stratz_client = StratzClient(config)

    @app_commands.command(
        name="ask", description="Ask AI questions about the Herald match in this thread"
    )
    @app_commands.describe(
        question="Your question about the match (e.g., 'Why did this game last so long?')"
    )
    async def ask_about_match(self, interaction: discord.Interaction, question: str):
        """AI-powered match analysis with comprehensive data integration."""

        # Defer response since this may take time
        await interaction.response.defer()

        try:
            # Validate we're in a match thread
            if not isinstance(interaction.channel, discord.Thread):
                embed = discord.Embed(
                    title="❌ Invalid Channel",
                    description="This command only works in Herald match discussion threads.",
                    color=0xFF0000,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Extract match ID from thread name
            match_id = self._extract_match_id(interaction.channel.name)
            if not match_id:
                embed = discord.Embed(
                    title="❌ Match ID Not Found",
                    description="Could not find match ID in thread name. Thread should contain 'Match 12345...'",
                    color=0xFF0000,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            logger.info(f"Processing /ask for match {match_id}: '{question[:100]}...'")

            # Try cache first for performance
            cached_data = await self.cache.get(match_id)
            if cached_data:
                match_details, stratz_data = cached_data
                logger.info(f"Using cached data for match {match_id}")
            else:
                # Fetch fresh data from APIs
                logger.info(f"Fetching fresh data for match {match_id}")

                # Parallel API calls for better performance
                tasks = [
                    self.opendota_client.get_match_details(match_id),
                    asyncio.sleep(self.config.api_delay_seconds),  # Rate limiting
                ]
                match_details, _ = await asyncio.gather(*tasks)

                # Get Stratz data
                stratz_data = await self.stratz_client.get_match_analysis(match_id)

                # Validate Herald match
                if not self.stratz_client.validate_herald_match(stratz_data):
                    embed = discord.Embed(
                        title="❌ Non-Herald Match",
                        description="This match contains players above Herald rank.",
                        color=0xFF0000,
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                # Cache for future use
                await self.cache.set(match_id, match_details, stratz_data)

            # Generate AI analysis
            ai_response = await self._generate_ai_analysis(
                match_id, match_details, stratz_data, question
            )

            # Send response as plain message
            formatted_response = f"Q:** {question}\n**A:** {ai_response}"
            await interaction.followup.send(formatted_response)

        except Exception as e:
            logger.error(f"Error processing /ask command: {e}")
            error_embed = discord.Embed(
                title="❌ Analysis Failed",
                description=f"Failed to analyze match: {str(e)[:200]}",
                color=0xFF0000,
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    def _extract_match_id(self, thread_name: str) -> Optional[int]:
        """Extract match ID from thread name pattern."""
        match = re.search(r"Match (\d+)", thread_name)
        return int(match.group(1)) if match else None

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
            temperature=0.5,
        )

        return response.choices[0].message.content.strip()


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    pass

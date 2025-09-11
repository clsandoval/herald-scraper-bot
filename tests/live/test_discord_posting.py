"""Live Discord posting tests - verifies messages actually reach Discord."""

import pytest
import discord
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.models.opendota import OpenDotaMatchDetail
from src.models.stratz import StratzMatchData, StratzPlayer
from src.discord.embeds import (
    create_match_summary_embed,
    create_team_analysis_embed,
    create_ai_response_embed,
)
from src.herald_reporter import HeraldMatchReporter


@pytest.mark.live
@pytest.mark.slow
class TestLiveDiscordPosting:
    """Test actual Discord message posting functionality."""

    @pytest.mark.asyncio
    async def test_basic_embed_posts_to_channel(self, live_test_channel, test_cleanup):
        """Test that a basic embed successfully posts to the live Discord channel."""
        # Create a simple test embed
        embed = discord.Embed(
            title="🧪 Live Test - Herald Bot",
            description="This is a test message to verify Discord posting works",
            color=0x00FF00,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Test Status", value="✅ Active", inline=True)
        embed.add_field(name="Test ID", value="live-discord-test-001", inline=True)
        embed.set_footer(text="Auto-generated test message")

        # Post to channel
        message = await live_test_channel.send(embed=embed)
        test_cleanup(message)

        # Verify message was posted
        assert message.id is not None
        assert len(message.embeds) == 1
        assert message.embeds[0].title == "🧪 Live Test - Herald Bot"

        # Verify we can fetch it back
        fetched_message = await live_test_channel.fetch_message(message.id)
        assert fetched_message.embeds[0].title == "🧪 Live Test - Herald Bot"

    @pytest.mark.asyncio
    async def test_herald_match_embed_posts_correctly(
        self, live_test_channel, test_cleanup
    ):
        """Test that Herald match embeds post with proper formatting."""
        # Create sample match data
        match_details = OpenDotaMatchDetail(
            match_id=8451070414,
            duration=5247,  # 87 minutes
            start_time=int(datetime.now(timezone.utc).timestamp()) - 3600,
            lobby_type=0,
            game_mode=1,
            radiant_win=True,
            players=[
                {
                    "player_slot": i,
                    "hero_id": i + 1,
                    "kills": i,
                    "deaths": i + 1,
                    "assists": i * 2,
                }
                for i in range(10)
            ],
        )

        # Create sample Stratz data
        sample_players = []
        for i in range(10):
            player = StratzPlayer(
                heroId=i + 1,
                kills=i,
                deaths=i + 1,
                assists=i * 2,
                level=25,
                heroDamage=15000 + i * 1000,
                isRadiant=i < 5,
                position=f"POSITION_{(i%5)+1}" if i < 5 else f"POSITION_{((i-5)%5)+1}",
            )
            sample_players.append(player)

        stratz_data = StratzMatchData(match_id=8451070414, players=sample_players)

        # Create Herald match embed
        match_embed = create_match_summary_embed(match_details, stratz_data)

        # Post to channel
        message = await live_test_channel.send(embed=match_embed)

        # Verify embed structure
        assert message.id is not None
        posted_embed = message.embeds[0]
        assert "Herald Match Analysis" in posted_embed.title
        assert str(match_details.match_id) in posted_embed.description
        assert (
            len(posted_embed.fields) >= 3
        )  # Should have date, duration, kill density, etc.

        # Verify clickable link works
        assert (
            f"https://stratz.com/matches/{match_details.match_id}" in posted_embed.url
        )

    @pytest.mark.asyncio
    async def test_thread_creation_and_posting(self, live_test_channel, test_cleanup):
        """Test creating match discussion threads and posting team analysis."""
        # Create initial match embed
        match_embed = discord.Embed(
            title="🏆 Herald Match Analysis - Test",
            description="**Match ID:** [8451070414](https://stratz.com/matches/8451070414)",
            color=0xFFD700,
        )
        match_embed.add_field(name="⏱️ Duration", value="87:27", inline=True)
        match_embed.add_field(name="💀 Total Kills", value="42", inline=True)

        # Post initial message
        initial_message = await live_test_channel.send(embed=match_embed)

        # Create thread from the message
        thread_name = f"Match 8451070414 - {datetime.now().strftime('%Y-%m-%d')}"
        thread = await initial_message.create_thread(name=thread_name)

        # Create team analysis embeds
        sample_radiant_players = [
            StratzPlayer(
                heroId=i + 1,
                kills=5 + i,
                deaths=2 + i,
                assists=8 + i,
                level=25,
                heroDamage=20000 + i * 2000,
                isRadiant=True,
                position=f"POSITION_{i+1}",
                item0Id=1 + i,
                item1Id=10 + i,
                item2Id=20 + i,
            )
            for i in range(5)
        ]

        radiant_embed = create_team_analysis_embed(sample_radiant_players, True)

        # Post team analysis to thread
        team_message = await thread.send(embed=radiant_embed)

        # Verify thread posting worked
        assert team_message.id is not None
        assert team_message.channel.id == thread.id
        posted_embed = team_message.embeds[0]
        assert "Radiant Team Analysis" in posted_embed.title
        assert len(posted_embed.fields) == 5  # One field per player

        # Verify thread is accessible and contains our message
        thread_messages = []
        async for msg in thread.history(limit=10):
            thread_messages.append(msg)

        assert len(thread_messages) >= 1
        assert any(
            "Radiant Team Analysis" in msg.embeds[0].title
            for msg in thread_messages
            if msg.embeds
        )

    @pytest.mark.asyncio
    async def test_ai_response_embed_posts(self, live_test_channel, test_cleanup):
        """Test AI response embeds post correctly to channel."""
        question = "Why did this Herald match last 87 minutes?"
        ai_response = """This Herald match lasted unusually long due to several factors:

1. **Poor farming efficiency** - Players had low GPM/XPM indicating inefficient resource gathering
2. **Indecisive team fights** - Multiple prolonged engagements without clear objectives
3. **Lack of high ground pressure** - Teams struggled to capitalize on advantages
4. **Conservative itemization** - Players built defensively rather than pushing for game-ending items

Herald players often struggle with game tempo and closing mechanics, leading to extended matches."""

        match_id = 8451070414

        # Create AI response embed
        ai_embed = create_ai_response_embed(question, ai_response, match_id)

        # Post to channel
        message = await live_test_channel.send(embed=ai_embed)

        # Verify AI response embed
        assert message.id is not None
        posted_embed = message.embeds[0]
        assert "AI Match Analysis" in posted_embed.title
        assert question in posted_embed.description
        assert "Herald match lasted unusually long" in posted_embed.fields[0].value
        assert f"Match {match_id}" in posted_embed.footer.text
        assert "GPT-4o-mini" in posted_embed.footer.text

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_periodic_reporter_posts_to_channel(
        self, live_discord_bot, live_test_channel, live_config, test_cleanup
    ):
        """Test the full Herald reporter workflow posts to live channel."""
        # Create reporter with live bot cache
        reporter = HeraldMatchReporter(live_config, live_discord_bot.match_cache)

        # Mock the API calls to avoid rate limiting and return predictable data
        sample_match_details = OpenDotaMatchDetail(
            match_id=9999999999,  # Fake match ID to avoid conflicts
            duration=5400,  # 90 minutes
            start_time=int(datetime.now(timezone.utc).timestamp()) - 7200,
            lobby_type=0,
            game_mode=1,
            radiant_win=False,
            players=[
                {
                    "player_slot": i,
                    "hero_id": i + 1,
                    "kills": i + 2,
                    "deaths": i + 1,
                    "assists": i * 3,
                    "leaver_status": 0,
                }
                for i in range(10)
            ],
        )

        sample_stratz_data = StratzMatchData(
            match_id=9999999999,
            players=[
                StratzPlayer(
                    heroId=i + 1,
                    kills=i + 2,
                    deaths=i + 1,
                    assists=i * 3,
                    level=25,
                    heroDamage=18000 + i * 1500,
                    isRadiant=i < 5,
                    position=f"POSITION_{(i%5)+1}",
                    steamAccount={"seasonRank": 12},  # Herald II
                )
                for i in range(10)
            ],
        )

        # Mock the API clients to return our test data
        with (
            patch.object(
                reporter.opendota_client,
                "get_match_details",
                return_value=sample_match_details,
            ),
            patch.object(
                reporter.stratz_client,
                "get_match_analysis",
                return_value=sample_stratz_data,
            ),
            patch.object(
                reporter.stratz_client, "validate_herald_match", return_value=True
            ),
        ):

            # Test the match processing and posting
            success = await reporter._process_and_post_match(
                9999999999, [live_test_channel]
            )

            assert success is True

            # Verify messages were posted to channel
            recent_messages = []
            async for message in live_test_channel.history(
                limit=5, after=datetime.now(timezone.utc) - timedelta(minutes=1)
            ):
                recent_messages.append(message)

            # Should have at least one message with Herald match embed
            herald_messages = [
                msg
                for msg in recent_messages
                if msg.embeds and "Herald Match Analysis" in msg.embeds[0].title
            ]
            assert len(herald_messages) >= 1

            # Check for thread creation
            herald_message = herald_messages[0]
            if herald_message.thread:
                test_cleanup(herald_message.thread)

                # Verify thread contains team analysis
                thread_messages = []
                async for msg in herald_message.thread.history(limit=10):
                    thread_messages.append(msg)

                team_analysis_messages = [
                    msg
                    for msg in thread_messages
                    if msg.embeds and ("Team Analysis" in msg.embeds[0].title)
                ]
                assert len(team_analysis_messages) >= 2  # Radiant + Dire

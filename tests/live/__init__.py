"""Live Discord testing module.

These tests connect to real Discord channels and verify that the bot
actually posts messages successfully. They require:

1. Real Discord bot token in DISCORD_BOT_TOKEN
2. Valid test channel ID in DISCORD_TEST_CHANNEL_ID  
3. Bot must have permissions in the test channel

Run with: uv run python -m pytest tests/live/ -m live -v

WARNING: These tests will post real messages to Discord channels.
Only run against dedicated test channels.
"""
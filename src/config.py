"""Unified configuration for Herald Discord Bot."""

import os
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Config(BaseModel):
    """Unified configuration supporting periodic and interactive features."""

    # Discord Configuration
    discord_bot_token: str = Field(..., description="Discord bot token")
    discord_test_channel_id: int = Field(
        ..., description="Test channel for posting matches"
    )
    discord_test_thread_id: int = Field(
        default=0, description="Test thread for development"
    )

    # API Configuration
    opendota_api_key: str = Field(..., description="OpenDota API key")
    stratz_api_token: str = Field(..., description="Stratz API bearer token")
    openai_api_key: str = Field(
        default="", description="OpenAI API key for interactive features"
    )

    # Bot Behavior
    query_days_back: int = Field(
        default=2, description="Days to look back for Herald matches"
    )
    thread_retention_days: int = Field(
        default=10, description="Days to retain match threads"
    )
    api_delay_seconds: int = Field(default=1, description="Delay between API calls")

    # Performance & Caching
    cache_ttl_hours: int = Field(default=4, description="Match data cache TTL")
    cache_max_entries: int = Field(default=100, description="Maximum cache entries")

    # OpenAI Configuration
    openai_timeout_seconds: int = Field(default=30, description="OpenAI API timeout")
    openai_max_retries: int = Field(default=2, description="OpenAI API retry attempts")
    openai_model: str = Field(
        default="gpt-4.1-mini", description="OpenAI model for analysis"
    )

    @field_validator("discord_test_channel_id")
    @classmethod
    def validate_discord_channel(cls, v):
        if v and v < 1000:
            raise ValueError("Discord channel ID must be valid snowflake")
        return v

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN", ""),
            discord_test_channel_id=int(os.getenv("DISCORD_TEST_CHANNEL_ID", "0")),
            discord_test_thread_id=int(os.getenv("DISCORD_TEST_THREAD_ID", "0")),
            opendota_api_key=os.getenv("OPENDOTA_API_KEY", ""),
            stratz_api_token=os.getenv("STRATZ_API_TOKEN", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            # Performance settings
            cache_ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "4")),
            cache_max_entries=int(os.getenv("CACHE_MAX_ENTRIES", "100")),
        )

    def validate_required(self) -> None:
        """Validate required configuration with helpful error messages."""
        required = {
            "discord_bot_token": "Discord bot token",
            "discord_test_channel_id": "Discord test channel ID",
            "opendota_api_key": "OpenDota API key",
            "stratz_api_token": "Stratz API token",
        }

        missing = [desc for field, desc in required.items() if not getattr(self, field)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

    @property
    def has_openai(self) -> bool:
        """Check if OpenAI functionality is available."""
        return bool(self.openai_api_key)

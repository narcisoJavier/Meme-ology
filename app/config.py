"""Application configuration settings using Pydantic Settings."""

from functools import lru_cache
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os


class Settings(BaseSettings):
    """Application and ingestion engine settings."""

    # General API Configuration
    APP_NAME: str = Field(default="Meme Tracker API", description="Application name")
    APP_ENV: str = Field(default="development", description="Environment (development, test, production)")
    DEBUG: bool = Field(default=True, description="Debug mode flag")
    HOST: str = Field(default="0.0.0.0", description="Bind host")
    PORT: int = Field(default=8000, description="Bind port")

    # Ingestion & Polling Configuration
    POLL_INTERVAL_SECONDS: int = Field(
        default=60,
        description="Interval in seconds between background ingestion runs",
    )
    OFFLINE_MODE: bool = Field(
        default=False,
        description="Force offline fixture ingestion fallback instead of live network calls",
    )
    REQUEST_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        description="Timeout for outbound HTTP requests in seconds",
    )
    MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retry attempts on rate limiting or transient errors",
    )

    # Source Feeds Configuration
    REDDIT_SUBREDDITS: List[str] = Field(
        default=["memes", "dankmemes", "me_irl", "GenAlpha", "wholesomememes", "AdviceAnimals"],
        description="List of subreddit names to monitor",
    )
    KYM_FEED_URLS: List[str] = Field(
        default=[
            "https://knowyourmeme.com/memes.rss",
            "https://knowyourmeme.com/news.rss",
        ],
        description="List of Know Your Meme RSS feed URLs",
    )
    BLUESKY_FEEDS: List[str] = Field(
        default=["meme", "trending-humor"],
        description="List of Bluesky search query feeds to monitor",
    )
    MASTODON_SERVERS: List[str] = Field(
        default=["mastodon.social"],
        description="List of Mastodon instance servers to monitor",
    )
    YOUTUBE_CHANNELS: List[str] = Field(
        default=[
            "UCaHT88aobpcvRFEuy4v5Clg",  # Lessons in Meme Culture (@LIMC)
            "UCbrPqq29C9Q_TQP7OFFRzcw",  # Know Your Meme Video (@KnowYourMeme)
            "UCq9UQ0TUfI9GyzSiZ2uNx5Q",  # Daily Dose of Memes (@DailyDoseOfMemes)
            "UC9sY9S-ddN-1E0jD2fFWLig",  # Grandayy (@grandayy)
            "UC2vpvibGYfBcb14l6CLVdiA",  # Memer Man (@MemerMan)
        ],
        description="List of YouTube channel IDs to monitor for meme content",
    )

    # Content Filtering
    ENGLISH_ONLY: bool = Field(
        default=True,
        description="Filter for English-only meme content across all sources",
    )

    # Webhook Alerts for Viral Breakouts
    DISCORD_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Discord Webhook URL for real-time viral meme breakout alerts",
    )
    SLACK_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Slack Incoming Webhook URL for viral meme alerts",
    )
    GENERIC_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Generic HTTP POST endpoint for viral meme alerts",
    )

    # Adaptive Viral Thresholds (velocity per hour)
    VIRAL_VELOCITY_REDDIT: float = Field(default=1000.0, description="Score growth/hr to trigger viral on Reddit")
    VIRAL_VELOCITY_YOUTUBE: float = Field(default=2500.0, description="Views growth/hr to trigger viral on YouTube")
    VIRAL_VELOCITY_FEDIVERSE: float = Field(default=250.0, description="Engagement growth/hr to trigger viral on Mastodon/Bluesky")

    # Persistence & Storage
    DB_PATH: str = Field(
        default="/tmp/memes.db" if os.environ.get("VERCEL") else "data/memes.db",
        description="Path to SQLite database file",
    )

    @field_validator("REDDIT_SUBREDDITS", "KYM_FEED_URLS", "BLUESKY_FEEDS", "MASTODON_SERVERS", "YOUTUBE_CHANNELS", mode="before")
    @classmethod
    def parse_list_fields(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            # Comma-separated list fallback
            return [item.strip().strip("'\"") for item in v.split(",") if item.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()

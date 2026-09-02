"""Data source status and health monitoring models."""

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, model_validator
from app.models.meme import SourcePlatform


class SourceStatus(BaseModel):
    """Health and metric status for an individual ingestion source feed."""

    id: Optional[str] = Field(
        default=None,
        description="Unique source ID, e.g. reddit_memes",
    )
    name: str = Field(
        ...,
        description="Source identifier, e.g. reddit:r/memes or Reddit r/memes",
    )
    platform: Union[SourcePlatform, str] = Field(
        ...,
        description="Source platform enum or string (reddit, knowyourmeme)",
    )
    community: Optional[str] = Field(
        default="",
        description="Subreddit name or feed category",
    )
    status: str = Field(
        default="ok",
        description="Health status: ok, degraded, failing, or offline",
    )
    item_count: int = Field(
        default=0,
        description="Number of memes successfully cached from this source",
    )
    last_synced_at: Optional[float] = Field(
        default=None,
        description="Unix timestamp of last successful sync",
    )
    last_error: Optional[str] = Field(
        default=None,
        description="Error message from last failed ingestion attempt",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Alias for last_error",
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="HTTP round-trip latency in milliseconds",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("id") and data.get("name"):
                data["id"] = data["name"].replace(":", "_").replace("/", "_").replace(" ", "_").lower()
            if not data.get("name") and data.get("id"):
                data["name"] = data["id"]
            if data.get("error_message") and not data.get("last_error"):
                data["last_error"] = data["error_message"]
            elif data.get("last_error") and not data.get("error_message"):
                data["error_message"] = data["last_error"]
        return data


class SourcesResponse(BaseModel):
    """Response payload for GET /api/v1/sources."""

    sources: List[SourceStatus] = Field(
        default_factory=list,
        description="List of configured source status objects",
    )
    total_sources: int = Field(default=0, description="Total number of sources")
    healthy_sources: int = Field(
        default=0,
        description="Count of currently healthy (status=ok) sources",
    )


class HealthResponse(BaseModel):
    """Response payload for GET /health."""

    status: str = Field(
        default="ok",
        description="Overall service health: ok, degraded, or unhealthy",
    )
    app_name: str = Field(default="Meme Tracker API", description="Service name")
    version: str = Field(default="0.1.0", description="Application version")
    uptime_seconds: float = Field(default=0.0, description="Seconds since service start")
    total_memes: Optional[int] = Field(
        default=0,
        description="Total distinct memes currently in cache",
    )
    total_memes_cached: Optional[int] = Field(
        default=0,
        description="Alias for total_memes",
    )
    healthy_sources: Optional[int] = Field(
        default=0,
        description="Count of healthy sources",
    )
    total_sources: Optional[int] = Field(
        default=0,
        description="Count of total sources",
    )
    sources: List[SourceStatus] = Field(
        default_factory=list,
        description="Health status of all data sources",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_health_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("total_memes") is not None and data.get("total_memes_cached") is None:
                data["total_memes_cached"] = data["total_memes"]
            elif data.get("total_memes_cached") is not None and data.get("total_memes") is None:
                data["total_memes"] = data["total_memes_cached"]
        return data

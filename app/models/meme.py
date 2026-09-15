"""Meme domain models and response schemas."""

from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field, model_validator
from app.core.dedup import compute_content_hash
from app.core.ranking import calculate_trending_score


class MediaType(str, Enum):
    """Supported media asset types."""
    IMAGE = "image"
    GIF = "gif"
    VIDEO = "video"
    LINK = "link"


class SourcePlatform(str, Enum):
    """Supported source platforms."""
    REDDIT = "reddit"
    BLUESKY = "bluesky"
    KNOWYOURMEME = "knowyourmeme"
    MASTODON = "mastodon"
    YOUTUBE = "youtube"


class LifecycleStage(str, Enum):
    """Virality lifecycle stages."""
    EMERGING = "emerging"
    VIRAL = "viral"
    PEAK = "peak"
    COOLING = "cooling"


class MemeGeneration(str, Enum):
    """Generational internet culture eras."""
    ALL = "all"
    GEN_ALPHA = "gen_alpha"      # Skibidi, Ohio, Rizz, Fanum Tax, Sigma, Mewing, Gyatt
    GEN_Z = "gen_z"              # Wojak, Dank, Barbenheimer, Goofy Ahh, Surreal, Deep-fried
    MILLENNIAL = "millennial"    # Doge, Drake, Distracted Boyfriend, Advice Animals, Bad Luck Brian
    GEN_X = "gen_x"              # Minions, LOLCats, Dancing Baby, Demotivational posters, Wholesome


class NormalizedMeme(BaseModel):
    """Internal normalized meme data contract produced by ingestion engine."""

    id: str = Field(
        ...,
        description="Globally unique meme identifier (e.g. reddit_memes_1d8xyz or kym_Entry-57336)",
    )
    raw_id: Optional[str] = Field(default=None, description="Original platform identifier")
    title: str = Field(..., description="Meme headline or title")
    media_url: str = Field(..., description="Direct URL to media file (image, gif, mp4)")
    media_type: MediaType = Field(
        default=MediaType.IMAGE,
        description="Type of media asset (image, gif, video, link)",
    )
    source_platform: Union[SourcePlatform, str] = Field(
        ...,
        description="Originating platform (reddit or knowyourmeme)",
    )
    source_community: str = Field(
        ...,
        description="Subreddit or KYM category (e.g. r/memes or confirmed)",
    )
    permalink: str = Field(..., description="Canonical link to original post/entry")
    author: str = Field(default="unknown", description="Author or creator username")
    score: int = Field(default=0, description="Upvotes or baseline engagement score")
    num_comments: int = Field(default=0, description="Comment count")
    created_at: float = Field(..., description="Unix epoch timestamp in seconds (UTC)")
    is_nsfw: bool = Field(default=False, description="NSFW flag")
    domain: str = Field(default="", description="Hosting domain of media asset")
    content_hash: Optional[str] = Field(
        default=None,
        description="Deterministic SHA-256 hash for deduplication",
    )
    trending_score: float = Field(
        default=0.0,
        description="Calculated engagement velocity score",
    )
    generation: Union[MemeGeneration, str] = Field(
        default=MemeGeneration.GEN_Z,
        description="Generational alignment (gen_alpha, gen_z, millennial, gen_x)",
    )
    is_short: bool = Field(
        default=False,
        description="Flag indicating if the media is a vertical short-form video (YouTube Shorts, etc.)",
    )
    source_category: str = Field(
        default="community_forum",
        description="Category classification: 'video_creator', 'community_forum', 'encyclopedia', 'federated_social'",
    )
    lifecycle_stage: str = Field(
        default="emerging",
        description="Virality lifecycle stage: 'emerging', 'viral', 'peak', 'cooling'",
    )
    velocity: float = Field(
        default=0.0,
        description="Engagement growth velocity (score or views per hour)",
    )
    acceleration: float = Field(
        default=0.0,
        description="Velocity rate of change (acceleration/deceleration)",
    )
    first_seen_at: Optional[float] = Field(
        default=None,
        description="Timestamp when meme was first observed by tracker",
    )
    last_seen_at: Optional[float] = Field(
        default=None,
        description="Timestamp when meme was last updated",
    )
    language: str = Field(
        default="en",
        description="ISO language code of meme text (e.g. en, de, fr, pt, es)",
    )
    country_code: str = Field(
        default="GLOBAL",
        description="Originating or primary country/region (e.g. US, DE, FR, BR, GLOBAL)",
    )

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("language") or not data.get("country_code"):
                from app.core.location import detect_meme_location
                detected_country, detected_lang = detect_meme_location(
                    title=data.get("title", ""),
                    source_community=data.get("source_community"),
                    source_platform=data.get("source_platform"),
                    author=data.get("author"),
                )
                if not data.get("country_code"):
                    data["country_code"] = detected_country
                if not data.get("language"):
                    data["language"] = detected_lang
            if not data.get("source_category"):
                plat_raw = data.get("source_platform")
                plat = (plat_raw.value if isinstance(plat_raw, SourcePlatform) else str(plat_raw or "")).lower()
                if "youtube" in plat:
                    data["source_category"] = "video_creator"
                elif "knowyourmeme" in plat or "kym" in plat:
                    data["source_category"] = "encyclopedia"
                elif "bluesky" in plat or "mastodon" in plat:
                    data["source_category"] = "federated_social"
                else:
                    data["source_category"] = "community_forum"

            if "is_short" not in data or data.get("is_short") is None:
                permalink = str(data.get("permalink") or "")
                title = str(data.get("title") or "")
                data["is_short"] = "/shorts/" in permalink or "#shorts" in title.lower()

            if not data.get("raw_id") and data.get("id"):
                data["raw_id"] = str(data["id"]).split("_")[-1]

            if not data.get("generation"):
                from app.core.classifier import classify_meme_generation
                data["generation"] = classify_meme_generation(
                    data.get("title", ""),
                    data.get("source_community"),
                    data.get("source_platform"),
                )

            if data.get("author") is None:
                data["author"] = "unknown"
            if data.get("domain") is None:
                data["domain"] = ""
            if data.get("title") is None:
                data["title"] = ""
            if data.get("permalink") is None:
                data["permalink"] = ""

            empty_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            current_hash = data.get("content_hash")
            if (not current_hash or current_hash == empty_sha256) and data.get("media_url") and data.get("title"):
                data["content_hash"] = compute_content_hash(data["media_url"], data["title"])

            if not data.get("trending_score") and data.get("created_at") is not None:
                try:
                    score = int(data.get("score") or 0)
                except (ValueError, TypeError):
                    score = 0
                try:
                    comments = int(data.get("num_comments") or 0)
                except (ValueError, TypeError):
                    comments = 0
                try:
                    created = float(data.get("created_at"))
                except (ValueError, TypeError):
                    created = 0.0
                data["trending_score"] = calculate_trending_score(score, comments, created)
        return data


class Meme(BaseModel):
    """Public API response schema representing a meme."""

    id: str = Field(..., description="Unique meme ID")
    title: str = Field(..., description="Meme title")
    url: str = Field(..., description="Direct media URL")
    media_url: str = Field(..., description="Direct media URL (alias for url)")
    media_type: MediaType = Field(default=MediaType.IMAGE, description="Media type")
    source: str = Field(..., description="Source platform name")
    source_platform: Union[SourcePlatform, str] = Field(..., description="Source platform enum")
    source_community: str = Field(..., description="Source community / subreddit / feed")
    permalink: str = Field(..., description="Permalink to original post")
    author: str = Field(default="unknown", description="Author username")
    score: int = Field(default=0, description="Engagement score / upvotes")
    num_comments: int = Field(default=0, description="Comment count")
    created_at: float = Field(..., description="Creation epoch timestamp in UTC")
    is_nsfw: bool = Field(default=False, description="NSFW flag")
    domain: str = Field(default="", description="Media domain")
    content_hash: str = Field(default="", description="Content hash")
    trending_score: float = Field(default=0.0, description="Trending score")
    generation: Union[MemeGeneration, str] = Field(
        default=MemeGeneration.GEN_Z,
        description="Generational alignment (gen_alpha, gen_z, millennial, gen_x)",
    )
    is_short: bool = Field(
        default=False,
        description="Vertical short-form video flag",
    )
    source_category: str = Field(
        default="community_forum",
        description="Category classification: 'video_creator', 'community_forum', 'encyclopedia', 'federated_social'",
    )
    lifecycle_stage: str = Field(
        default="emerging",
        description="Virality lifecycle stage: 'emerging', 'viral', 'peak', 'cooling'",
    )
    velocity: float = Field(
        default=0.0,
        description="Engagement growth velocity (score or views per hour)",
    )
    acceleration: float = Field(
        default=0.0,
        description="Velocity rate of change (acceleration/deceleration)",
    )
    first_seen_at: Optional[float] = Field(
        default=None,
        description="Timestamp when meme was first observed by tracker",
    )
    last_seen_at: Optional[float] = Field(
        default=None,
        description="Timestamp when meme was last updated",
    )
    language: str = Field(
        default="en",
        description="ISO language code of meme text (e.g. en, de, fr, pt, es)",
    )
    country_code: str = Field(
        default="GLOBAL",
        description="Originating or primary country/region (e.g. US, DE, FR, BR, GLOBAL)",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("language") or not data.get("country_code"):
                from app.core.location import detect_meme_location
                detected_country, detected_lang = detect_meme_location(
                    title=data.get("title", ""),
                    source_community=data.get("source_community"),
                    source_platform=data.get("source_platform") or data.get("source"),
                    author=data.get("author"),
                )
                if not data.get("country_code"):
                    data["country_code"] = detected_country
                if not data.get("language"):
                    data["language"] = detected_lang
            if not data.get("source_category"):
                plat_raw = data.get("source_platform") or data.get("source")
                plat = (plat_raw.value if isinstance(plat_raw, SourcePlatform) else str(plat_raw or "")).lower()
                if "youtube" in plat:
                    data["source_category"] = "video_creator"
                elif "knowyourmeme" in plat or "kym" in plat:
                    data["source_category"] = "encyclopedia"
                elif "bluesky" in plat or "mastodon" in plat:
                    data["source_category"] = "federated_social"
                else:
                    data["source_category"] = "community_forum"

            if "is_short" not in data or data.get("is_short") is None:
                permalink = str(data.get("permalink") or "")
                title = str(data.get("title") or "")
                data["is_short"] = "/shorts/" in permalink or "#shorts" in title.lower()

            if not data.get("generation"):
                from app.core.classifier import classify_meme_generation
                data["generation"] = classify_meme_generation(
                    data.get("title", ""),
                    data.get("source_community"),
                    data.get("source_platform") or data.get("source"),
                )

            if data.get("author") is None:
                data["author"] = "unknown"
            if data.get("domain") is None:
                data["domain"] = ""
            if data.get("title") is None:
                data["title"] = ""
            if data.get("permalink") is None:
                data["permalink"] = ""
            if data.get("content_hash") is None:
                data["content_hash"] = ""

            if "media_url" in data and "url" not in data:
                data["url"] = data["media_url"]
            elif "url" in data and "media_url" not in data:
                data["media_url"] = data["url"]

            if "source_platform" in data and "source" not in data:
                sp = data["source_platform"]
                data["source"] = sp.value if isinstance(sp, SourcePlatform) else str(sp)
            elif "source" in data and "source_platform" not in data:
                data["source_platform"] = data["source"]
        elif hasattr(data, "__dict__"):
            media_url = getattr(data, "media_url", getattr(data, "url", ""))
            source_platform = getattr(data, "source_platform", getattr(data, "source", SourcePlatform.REDDIT))
            source_str = source_platform.value if isinstance(source_platform, SourcePlatform) else str(source_platform)
            return {
                "id": getattr(data, "id"),
                "title": getattr(data, "title") or "",
                "url": media_url,
                "media_url": media_url,
                "media_type": getattr(data, "media_type", MediaType.IMAGE),
                "source": source_str,
                "source_platform": source_platform,
                "source_community": getattr(data, "source_community", ""),
                "permalink": getattr(data, "permalink", "") or "",
                "author": getattr(data, "author", "unknown") or "unknown",
                "score": getattr(data, "score", 0),
                "num_comments": getattr(data, "num_comments", 0),
                "created_at": getattr(data, "created_at", 0.0),
                "is_nsfw": getattr(data, "is_nsfw", False),
                "domain": getattr(data, "domain", "") or "",
                "content_hash": getattr(data, "content_hash", "") or "",
                "trending_score": getattr(data, "trending_score", 0.0),
                "generation": getattr(data, "generation", MemeGeneration.GEN_Z),
                "is_short": getattr(data, "is_short", False),
                "source_category": getattr(data, "source_category", "community_forum"),
                "lifecycle_stage": getattr(data, "lifecycle_stage", "emerging"),
                "velocity": getattr(data, "velocity", 0.0),
                "acceleration": getattr(data, "acceleration", 0.0),
                "first_seen_at": getattr(data, "first_seen_at", None),
                "last_seen_at": getattr(data, "last_seen_at", None),
                "language": getattr(data, "language", "en") or "en",
                "country_code": getattr(data, "country_code", "GLOBAL") or "GLOBAL",
            }
        return data

    @classmethod
    def from_normalized(cls, norm: NormalizedMeme) -> "Meme":
        """Convert a NormalizedMeme to public Meme model."""
        source_val = norm.source_platform.value if isinstance(norm.source_platform, SourcePlatform) else str(norm.source_platform)
        return cls(
            id=norm.id,
            title=norm.title,
            url=norm.media_url,
            media_url=norm.media_url,
            media_type=norm.media_type,
            source=source_val,
            source_platform=norm.source_platform,
            source_community=norm.source_community,
            permalink=norm.permalink,
            author=norm.author,
            score=norm.score,
            num_comments=norm.num_comments,
            created_at=norm.created_at,
            is_nsfw=norm.is_nsfw,
            domain=norm.domain,
            content_hash=norm.content_hash or "",
            trending_score=norm.trending_score,
            generation=norm.generation,
            is_short=getattr(norm, "is_short", False),
            source_category=getattr(norm, "source_category", "community_forum"),
            lifecycle_stage=getattr(norm, "lifecycle_stage", "emerging"),
            velocity=getattr(norm, "velocity", 0.0),
            acceleration=getattr(norm, "acceleration", 0.0),
            first_seen_at=getattr(norm, "first_seen_at", None),
            last_seen_at=getattr(norm, "last_seen_at", None),
            language=getattr(norm, "language", "en") or "en",
            country_code=getattr(norm, "country_code", "GLOBAL") or "GLOBAL",
        )


class PaginatedResponse(BaseModel):
    """Paginated collection of meme items."""

    items: List[Union[Meme, NormalizedMeme]] = Field(
        default_factory=list, description="List of meme items"
    )
    total: int = Field(default=0, description="Total matching meme count")
    limit: int = Field(default=20, description="Page limit")
    offset: int = Field(default=0, description="Page offset")
    has_more: bool = Field(default=False, description="Flag indicating if more items exist")


# Alias for backward compatibility
PaginatedMemeResponse = PaginatedResponse


class TrendingTopic(BaseModel):
    """Viral topic or hashtag trending globally."""
    topic: str = Field(..., description="Topic label or hashtag")
    count: int = Field(default=1, description="Number of active viral memes in cluster")
    trending_score: float = Field(default=0.0, description="Aggregated virality score")


class GlobalTrendsResponse(BaseModel):
    """Global trending topics and cross-platform viral memes."""
    timestamp: float = Field(..., description="UTC epoch timestamp of trend snapshot")
    top_topics: List[TrendingTopic] = Field(default_factory=list, description="Top viral topics globally")
    top_memes: List[Meme] = Field(default_factory=list, description="Top global trending memes")
    active_regions: List[str] = Field(default_factory=list, description="Active participating countries/regions")

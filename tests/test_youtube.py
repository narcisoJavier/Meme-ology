"""Unit tests for YouTube RSS feed meme extraction."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ingestion.youtube import YouTubeFetcher
from app.models.meme import MediaType, NormalizedMeme, SourcePlatform


SAMPLE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="http://www.youtube.com/feeds/videos.xml?channel_id=UCaHT88aobpcvRFEuy4v5Clg"/>
  <id>yt:channel:aHT88aobpcvRFEuy4v5Clg</id>
  <yt:channelId>aHT88aobpcvRFEuy4v5Clg</yt:channelId>
  <title>Lessons in Meme Culture</title>
  <author>
    <name>Lessons in Meme Culture</name>
    <uri>https://www.youtube.com/channel/UCaHT88aobpcvRFEuy4v5Clg</uri>
  </author>
  <published>2017-06-06T06:42:26+00:00</published>
  <entry>
    <id>yt:video:5ctTVpQstC0</id>
    <yt:videoId>5ctTVpQstC0</yt:videoId>
    <yt:channelId>UCaHT88aobpcvRFEuy4v5Clg</yt:channelId>
    <title>Aura Farm Battles Are Here</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=5ctTVpQstC0"/>
    <author>
      <name>Lessons in Meme Culture</name>
      <uri>https://www.youtube.com/channel/UCaHT88aobpcvRFEuy4v5Clg</uri>
    </author>
    <published>2026-09-02T13:00:06+00:00</published>
    <updated>2026-09-02T13:00:09+00:00</updated>
    <media:group>
      <media:title>Aura Farm Battles Are Here</media:title>
      <media:content url="https://www.youtube.com/v/5ctTVpQstC0?version=3" type="application/x-shockwave-flash" width="640" height="390"/>
      <media:thumbnail url="https://i2.ytimg.com/vi/5ctTVpQstC0/hqdefault.jpg" width="480" height="360"/>
      <media:description>AURA meme analysis</media:description>
      <media:community>
        <media:starRating count="6482" average="5.00" min="1" max="5"/>
        <media:statistics views="333193"/>
      </media:community>
    </media:group>
  </entry>
  <entry>
    <id>yt:video:UMOahnOyInA</id>
    <yt:videoId>UMOahnOyInA</yt:videoId>
    <title>What's With Fix Mojang Bedrock Comments?</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=UMOahnOyInA"/>
    <author>
      <name>Lessons in Meme Culture</name>
    </author>
    <published>2026-09-01T13:00:35+00:00</published>
    <media:group>
      <media:thumbnail url="https://i.ytimg.com/vi/UMOahnOyInA/hqdefault.jpg"/>
      <media:community>
        <media:starRating count="16054"/>
        <media:statistics views="654967"/>
      </media:community>
    </media:group>
  </entry>
</feed>
"""


class TestYouTubeFetcher:
    """Tests for YouTube RSS feed ingestion and parsing."""

    def test_parse_atom_xml(self) -> None:
        """Verify Atom XML parsing extracts correct fields and attributes."""
        fetcher = YouTubeFetcher(channel_id="UCaHT88aobpcvRFEuy4v5Clg")
        memes = fetcher.parse_atom_xml(SAMPLE_ATOM_XML)

        assert len(memes) == 2

        m1 = memes[0]
        assert m1.id == "youtube_5ctTVpQstC0"
        assert m1.raw_id == "5ctTVpQstC0"
        assert m1.title == "Aura Farm Battles Are Here"
        assert m1.media_type == MediaType.VIDEO
        assert m1.source_platform == SourcePlatform.YOUTUBE
        assert m1.source_community == "Lessons in Meme Culture"
        assert m1.author == "Lessons in Meme Culture"
        assert m1.permalink == "https://www.youtube.com/watch?v=5ctTVpQstC0"
        assert "5ctTVpQstC0" in m1.media_url
        assert m1.score == 333193
        assert m1.num_comments == 6482
        assert m1.domain == "youtube.com"
        assert not m1.is_nsfw

        m2 = memes[1]
        assert m2.id == "youtube_UMOahnOyInA"
        assert m2.score == 654967
        assert m2.num_comments == 16054

    def test_parse_youtube_shorts_detection(self) -> None:
        """Verify that /shorts/ URLs are detected and marked as is_short=True."""
        xml_with_short = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
          <title>Know Your Meme</title>
          <entry>
            <id>yt:video:O-LkmmyQDfM</id>
            <yt:videoId>O-LkmmyQDfM</yt:videoId>
            <title>The 'Had to Do It to Em' Guy Was Arrested?</title>
            <link rel="alternate" href="https://www.youtube.com/shorts/O-LkmmyQDfM"/>
            <author><name>Know Your Meme</name></author>
            <published>2026-08-27T20:19:39+00:00</published>
            <media:group>
              <media:thumbnail url="https://i4.ytimg.com/vi/O-LkmmyQDfM/hqdefault.jpg"/>
              <media:community>
                <media:statistics views="45200"/>
              </media:community>
            </media:group>
          </entry>
        </feed>
        """
        fetcher = YouTubeFetcher(channel_id="UCbrPqq29C9Q_TQP7OFFRzcw")
        memes = fetcher.parse_atom_xml(xml_with_short)
        assert len(memes) == 1
        assert memes[0].is_short is True
        assert memes[0].source_category == "video_creator"
        assert memes[0].permalink == "https://www.youtube.com/shorts/O-LkmmyQDfM"

    def test_parse_malformed_xml_graceful(self) -> None:
        """Malformed XML should return an empty list without crashing."""
        fetcher = YouTubeFetcher()
        memes = fetcher.parse_atom_xml("not valid xml <<< >>>")
        assert memes == []

    def test_offline_fixtures_loading(self, tmp_path: Path) -> None:
        """Verify load_offline_fixtures reads from JSON fixture correctly."""
        fixture_data = [
            {
                "raw_id": "test_video_123",
                "title": "Test YouTube Meme",
                "media_url": "https://i.ytimg.com/vi/test_video_123/hqdefault.jpg",
                "score": 50000,
                "num_comments": 1200,
                "created_at": 1788000000.0,
                "source_community": "LIMC",
                "permalink": "https://www.youtube.com/watch?v=test_video_123",
                "author": "Lessons in Meme Culture",
            }
        ]
        fix_file = tmp_path / "youtube_test.json"
        fix_file.write_text(json.dumps(fixture_data), encoding="utf-8")

        fetcher = YouTubeFetcher(fixture_json_path=fix_file)
        memes = fetcher.load_offline_fixtures()

        assert len(memes) == 1
        assert memes[0].id == "youtube_test_video_123"
        assert memes[0].title == "Test YouTube Meme"
        assert memes[0].source_platform == SourcePlatform.YOUTUBE
        assert fetcher.status.status == "ok"

    @pytest.mark.asyncio
    async def test_live_fetch_success(self) -> None:
        """Verify successful live HTTP request returns normalized memes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_ATOM_XML

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        fetcher = YouTubeFetcher(http_client=mock_client)
        memes = await fetcher.fetch_memes()

        assert len(memes) == 2
        assert fetcher.status.status == "ok"
        assert fetcher.status.item_count == 2

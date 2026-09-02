"""Adversarial tests for Reddit ingestion."""
import html, json, pytest, time
from typing import Any, Dict, List
from app.ingestion.reddit import RedditFetcher, parse_reddit_listing
from app.models.meme import MediaType, NormalizedMeme, Meme, PaginatedResponse, SourcePlatform

class TestAdversarialRedditIngestion:
    @pytest.fixture
    def fetcher(self) -> RedditFetcher:
        return RedditFetcher(subreddit="memes")

    @pytest.mark.parametrize("bad_input", [
        "", "   ", "{", "{invalid json}", "[1, 2, 3]", "12345", "null", "true", "false", "<xml>not json</xml>"
    ])
    def test_malformed_json_strings(self, fetcher: RedditFetcher, bad_input: str):
        result = fetcher.parse_listing_json(bad_input)
        assert isinstance(result, list)
        assert result == []

    @pytest.mark.parametrize("bad_dict", [
        dict(), dict(data=None), dict(data="not a dict"), dict(data=[]), dict(data=12345),
        dict(data=dict(children=None)), dict(data=dict(children="not a list")), dict(data=dict(children=123))
    ])
    def test_malformed_data_structure(self, fetcher: RedditFetcher, bad_dict: dict):
        result = fetcher.parse_listing_dict(bad_dict)
        assert isinstance(result, list)
        assert result == []

    def test_children_with_null_and_non_dict_elements(self, fetcher: RedditFetcher):
        valid_post = dict(id="valid1", title="Valid Meme 1", url="https://i.redd.it/valid1.jpg", domain="i.redd.it", author="user1", score=100, num_comments=10, created_utc=1700000000.0)
        payload = dict(data=dict(children=[None, "string_child", 123, [], dict(), dict(data=None), dict(data="str_data"), dict(data=valid_post), None]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert memes[0].raw_id == "valid1"

    def test_null_domain_handling(self, fetcher: RedditFetcher):
        post = dict(id="nulldomain1", title="Null domain post", url="https://i.redd.it/test.jpg", domain=None, author="user_null", score=50, num_comments=5, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert memes[0].raw_id == "nulldomain1"

    def test_null_author_handling(self, fetcher: RedditFetcher):
        post = dict(id="nullauthor1", title="Null author post", url="https://i.redd.it/test.jpg", domain="i.redd.it", author=None, score=50, num_comments=5, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert memes[0].author == "unknown" or isinstance(memes[0].author, str)

    def test_null_title_and_permalink_handling(self, fetcher: RedditFetcher):
        post = dict(id="nulltitle1", title=None, url="https://i.redd.it/test.jpg", domain="i.redd.it", permalink=None, author="some_author", score=10, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert isinstance(memes[0].title, str)
        assert isinstance(memes[0].permalink, str)

    @pytest.mark.parametrize("post_override, should_exclude", [
        (dict(stickied=True), True),
        (dict(pinned=True), True),
        (dict(is_self=True), True),
        (dict(author="[deleted]"), True),
        (dict(selftext="[removed]"), True),
        (dict(id=""), True),
        (dict(id=None), True),
        (dict(url=""), True),
        (dict(url=None), True),
    ])
    def test_post_filtering_rules(self, fetcher: RedditFetcher, post_override: dict, should_exclude: bool):
        base_post = dict(id="filter_test_id", title="Normal Filter Test Post", url="https://i.redd.it/normal.png", domain="i.redd.it", author="normal_author", score=500, num_comments=20, created_utc=1700000000.0, stickied=False, is_self=False, pinned=False)
        base_post.update(post_override)
        payload = dict(data=dict(children=[dict(data=base_post)]))
        memes = fetcher.parse_listing_dict(payload)
        if should_exclude:
            assert len(memes) == 0
        else:
            assert len(memes) == 1

    def test_gallery_with_valid_metadata(self, fetcher: RedditFetcher):
        post = dict(id="gal_valid", title="Valid Gallery Post", is_gallery=True, gallery_data=dict(items=[dict(media_id="img_001")]), media_metadata=dict(img_001=dict(status="valid", e="Image", m="image/jpg", s=dict(u="https://preview.redd.it/gal001.jpg?width=1080&amp;s=abcdef"))), author="gallery_user", score=350, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert "gal001.jpg" in memes[0].media_url
        assert "&amp;" not in memes[0].media_url
        assert memes[0].media_type == MediaType.IMAGE

    def test_gallery_with_gif_media_type(self, fetcher: RedditFetcher):
        post = dict(id="gal_gif", title="Gallery GIF Post", is_gallery=True, gallery_data=dict(items=[dict(media_id="gif_001")]), media_metadata=dict(gif_001=dict(m="image/gif", s=dict(gif="https://preview.redd.it/anim.gif?s=123"))), author="gallery_user", score=350, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert memes[0].media_type == MediaType.GIF

    @pytest.mark.parametrize("bad_gallery_data, bad_metadata", [
        (None, None), (dict(), dict()), (dict(items=[]), dict()),
        (dict(items=[dict(media_id="missing_id")]), dict(other_id=dict(s=dict(u="https://i.redd.it/other.jpg")))),
        (dict(items=[None]), dict(key=None)),
        (dict(items=[dict(media_id="id1")]), dict(id1=None)),
        (dict(items=[dict(media_id="id1")]), dict(id1=dict(s=None))),
        (dict(items=[dict(media_id="id1")]), dict(id1=dict(s=dict(), p=[]))),
    ])
    def test_malformed_gallery_structures(self, fetcher: RedditFetcher, bad_gallery_data: Any, bad_metadata: Any):
        post = dict(id="gal_bad_test", title="Bad Gallery", is_gallery=True, gallery_data=bad_gallery_data, media_metadata=bad_metadata, author="user", score=10, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert isinstance(memes, list)

    def test_html_entity_unescaping_in_title_and_url(self, fetcher: RedditFetcher):
        post = dict(id="html_test_1", title="Me &amp; the boys &quot;debugging&quot; &lt;code&gt; &#39;test&#39;", url="https://preview.redd.it/meme.jpg?width=1080&amp;crop=smart&amp;auto=webp&amp;s=abc123xyz", domain="preview.redd.it", author="coder_1", score=999, created_utc=1700000000.0, permalink="/r/memes/comments/html_test_1/me_&amp;_the_boys/")
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        m = memes[0]
        assert "&amp;" not in m.title
        assert "debugging" in m.title
        assert "&amp;" not in m.media_url
        assert "width=1080&crop=smart" in m.media_url

    def test_native_video_fallback_url(self, fetcher: RedditFetcher):
        post = dict(id="vid_vreddit", title="Funny video meme", is_video=True, domain="v.redd.it", url="https://v.redd.it/xyz123", media=dict(reddit_video=dict(fallback_url="https://v.redd.it/xyz123/DASH_720.mp4?source=fallback&amp;s=999", height=720, width=1280, is_gif=False)), author="video_creator", score=2500, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        m = memes[0]
        assert m.media_type == MediaType.VIDEO
        assert m.media_url == "https://v.redd.it/xyz123/DASH_720.mp4?source=fallback&s=999"

    def test_native_video_in_secure_media(self, fetcher: RedditFetcher):
        post = dict(id="vid_sec_media", title="Secure media video", is_video=True, url="https://v.redd.it/sec456", media=None, secure_media=dict(reddit_video=dict(fallback_url="https://v.redd.it/sec456/DASH_480.mp4")), author="video_creator", score=1200, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert memes[0].media_type == MediaType.VIDEO
        assert "DASH_480.mp4" in memes[0].media_url

    def test_gifv_converts_to_mp4(self, fetcher: RedditFetcher):
        post = dict(id="gifv_post", title="High quality gifv meme", url="https://i.imgur.com/highqual.gifv", domain="i.imgur.com", author="user", score=800, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert memes[0].media_url == "https://i.imgur.com/highqual.mp4"
        assert memes[0].media_type == MediaType.VIDEO

    @pytest.mark.parametrize("imgur_url, expected_media_url", [
        ("https://imgur.com/a/ABC123xyz", "https://i.imgur.com/ABC123xyz.jpg"),
        ("http://imgur.com/gallery/DEF456", "https://i.imgur.com/DEF456.jpg"),
        ("https://imgur.com/GHI789", "https://i.imgur.com/GHI789.jpg"),
        ("https://i.imgur.com/JKL012.png", "https://i.imgur.com/JKL012.png"),
    ])
    def test_imgur_url_normalization(self, fetcher: RedditFetcher, imgur_url: str, expected_media_url: str):
        post = dict(id="imgur_test", title="Imgur Meme", url=imgur_url, domain="imgur.com", author="imgur_user", score=300, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert memes[0].media_url == expected_media_url

    def test_extreme_numerical_values(self, fetcher: RedditFetcher):
        post1 = dict(id="extreme_nums", title="Extreme Numbers Meme", url="https://i.redd.it/extreme.jpg", domain="i.redd.it", author="math_wizard", score=2**31 - 1, num_comments=10_000_000, created_utc=1700000000.0)
        post2 = dict(id="negative_score", title="Downvoted Meme", url="https://i.redd.it/downvoted.jpg", domain="i.redd.it", author="unpopular_guy", score=-500, num_comments=0, created_utc=1700000000.0)
        payload = dict(data=dict(children=[dict(data=post1), dict(data=post2)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 2
        assert memes[0].score == 2**31 - 1
        assert memes[0].num_comments == 10_000_000
        assert memes[0].trending_score > 0
        assert memes[1].score == -500

    def test_crosspost_parent_resolution(self, fetcher: RedditFetcher):
        parent = dict(url="https://i.redd.it/original_source.png", post_hint="image", domain="i.redd.it")
        post = dict(id="crosspost_1", title="Crossposted funny meme", url="https://www.reddit.com/r/memes/comments/crosspost_1/", domain="reddit.com", author="crossposter", score=750, num_comments=45, created_utc=1700000000.0, crosspost_parent_list=[parent])
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert len(memes) == 1
        assert memes[0].media_url == "https://i.redd.it/original_source.png"
        assert memes[0].media_type == MediaType.IMAGE

    def test_crosspost_parent_malformed_items(self, fetcher: RedditFetcher):
        post = dict(id="crosspost_bad", title="Crosspost with bad parent", url="https://www.reddit.com/r/memes/comments/crosspost_bad/", domain="reddit.com", author="crossposter", score=750, created_utc=1700000000.0, crosspost_parent_list=[None, "invalid", dict()])
        payload = dict(data=dict(children=[dict(data=post)]))
        memes = fetcher.parse_listing_dict(payload)
        assert isinstance(memes, list)

    def test_normalized_meme_to_meme_model_conversion(self):
        norm = NormalizedMeme(id="reddit_memes_test123", raw_id="test123", title="Test Meme Title", media_url="https://i.redd.it/test.jpg", media_type=MediaType.IMAGE, source_platform=SourcePlatform.REDDIT, source_community="r/memes", permalink="https://www.reddit.com/r/memes/comments/test123/", author="test_user", score=1200, num_comments=50, created_at=1700000000.0, is_nsfw=False, domain="i.redd.it", content_hash="abc123hash", trending_score=42.5)
        meme = Meme.from_normalized(norm)
        assert meme.id == norm.id
        assert meme.title == norm.title
        assert meme.url == norm.media_url
        assert meme.media_url == norm.media_url
        assert meme.source == "reddit"
        assert meme.trending_score == 42.5
        page = PaginatedResponse(items=[meme], total=1, limit=20, offset=0, has_more=False)
        dumped = page.model_dump_json()
        restored = PaginatedResponse.model_validate_json(dumped)
        assert restored.total == 1
        assert len(restored.items) == 1
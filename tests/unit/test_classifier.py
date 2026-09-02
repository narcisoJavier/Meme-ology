"""Unit tests for generational meme classification engine."""

import pytest
from app.core.classifier import classify_meme_generation
from app.models.meme import Meme, MemeGeneration, NormalizedMeme, SourcePlatform


class TestGenerationalClassifier:
    """Validate lexical and community-based generational categorization."""

    @pytest.mark.parametrize(
        "title,community,expected",
        [
            ("Me when the Skibidi Toilet attacks the camera crew", "r/memes", "gen_alpha"),
            ("Only in Ohio bruh Fanum tax is real", "r/dankmemes", "gen_alpha"),
            ("Bro has unspoken rizz and a 100-day mewing streak", "r/memes", "gen_alpha"),
            ("Kai Cenat meeting Baby Gronk", "r/memes", "gen_alpha"),
            ("Random post with no keywords", "r/GenAlpha", "gen_alpha"),
            ("Post in skibidi toilet subreddit", "r/skibiditoilet", "gen_alpha"),
        ],
    )
    def test_classify_gen_alpha(self, title: str, community: str, expected: str) -> None:
        result = classify_meme_generation(title=title, source_community=community)
        assert result == expected

    @pytest.mark.parametrize(
        "title,community,expected",
        [
            ("Wojak crying over his portfolio", "r/dankmemes", "gen_z"),
            ("Average Enjoyer GigaChad gym motivation", "r/memes", "gen_z"),
            ("Barbenheimer double feature premiere", "trending", "gen_z"),
            ("Goofy ahh audio meme compilation", "r/me_irl", "gen_z"),
            ("Random meme in GenZ subreddit", "r/GenZ", "gen_z"),
        ],
    )
    def test_classify_gen_z(self, title: str, community: str, expected: str) -> None:
        result = classify_meme_generation(title=title, source_community=community)
        assert result == expected

    @pytest.mark.parametrize(
        "title,community,expected",
        [
            ("Distracted Boyfriend looking at new code", "confirmed", "millennial"),
            ("Much code, very wow Doge", "r/memes", "millennial"),
            ("Drake hotline bling approval", "r/memes", "millennial"),
            ("Bad Luck Brian compiles with zero errors, deletes DB", "r/AdviceAnimals", "millennial"),
            ("Post in AdviceAnimals subreddit", "r/AdviceAnimals", "millennial"),
        ],
    )
    def test_classify_millennial(self, title: str, community: str, expected: str) -> None:
        result = classify_meme_generation(title=title, source_community=community)
        assert result == expected

    @pytest.mark.parametrize(
        "title,community,expected",
        [
            ("Minion saying don't talk to me before my coffee", "r/memes", "gen_x"),
            ("I Can Haz Cheezburger classic", "confirmed", "gen_x"),
            ("Dancing baby on old CRT monitor", "r/memes", "gen_x"),
            ("All Your Base Are Belong To Us", "confirmed", "gen_x"),
            ("Wholesome dog greeting you after long day", "r/wholesomememes", "gen_x"),
        ],
    )
    def test_classify_gen_x_boomer(self, title: str, community: str, expected: str) -> None:
        result = classify_meme_generation(title=title, source_community=community)
        assert result == expected

    def test_normalized_meme_auto_classification(self) -> None:
        """NormalizedMeme automatically populates generation if omitted."""
        meme = NormalizedMeme(
            id="test_alpha_01",
            title="Skibidi Toilet Rizz in Ohio",
            media_url="https://api.memegen.link/images/fine.jpg",
            source_platform=SourcePlatform.REDDIT,
            source_community="r/memes",
            permalink="https://reddit.com/r/memes",
            created_at=1700000000.0,
        )
        assert meme.generation == "gen_alpha"

    def test_meme_from_normalized_preserves_generation(self) -> None:
        """Converting NormalizedMeme to public Meme preserves generation."""
        norm = NormalizedMeme(
            id="test_millennial_01",
            title="Doge much wow",
            media_url="https://api.memegen.link/images/doge.jpg",
            source_platform=SourcePlatform.REDDIT,
            source_community="r/AdviceAnimals",
            permalink="https://reddit.com/r/AdviceAnimals",
            created_at=1700000000.0,
            generation="millennial",
        )
        public_meme = Meme.from_normalized(norm)
        assert public_meme.generation == "millennial"

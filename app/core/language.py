"""Language detection and English-only filtering utilities."""

from __future__ import annotations

import re
from typing import Optional

# Non-English Unicode script ranges (Cyrillic, Arabic, CJK, Devanagari, Hangul, Hebrew, Thai, Greek, etc.)
NON_LATIN_SCRIPT_PATTERN = re.compile(
    r"[\u0400-\u04FF"  # Cyrillic
    r"\u0600-\u06FF"  # Arabic
    r"\u4E00-\u9FFF"  # CJK Unified Ideographs (Chinese)
    r"\u3040-\u309F"  # Hiragana (Japanese)
    r"\u30A0-\u30FF"  # Katakana (Japanese)
    r"\uAC00-\uD7AF"  # Hangul (Korean)
    r"\u0900-\u097F"  # Devanagari (Hindi)
    r"\u0590-\u05FF"  # Hebrew
    r"\u0E00-\u0E7F"  # Thai
    r"\u0370-\u03FF]"  # Greek
)

# Characteristic non-English punctuation/characters in Latin-script languages
NON_ENGLISH_CHARS_PATTERN = re.compile(r"[¿¡ğüşöı]")

# Common high-frequency English words and internet meme vocabulary
COMMON_ENGLISH_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "is", "are", "was", "were", "been",
    "meme", "memes", "bro", "lol", "guy", "relatable", "funny", "pov",
    "real", "why", "where", "how", "aura", "skibidi", "rizz", "ngl",
    "tbh", "goat", "sigma", "bussing", "cook", "cooked", "cap", "nocap"
}

# Common high-frequency non-English indicator words (Spanish, Portuguese, German, French, Turkish, Italian)
FOREIGN_INDICATOR_WORDS = {
    # Spanish
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "en", "que", "por",
    "para", "con", "del", "al", "es", "son", "pero", "como", "mas", "aqui", "ahi",
    "esta", "este", "llevo", "minutos", "usted", "sigue", "comiendo", "mirar",
    "garganta", "momento", "necesito", "palito", "doctor", "tiempo", "ahora",
    # French
    "le", "les", "des", "du", "dans", "avec", "pour", "est", "sont", "cette", "cet",
    "nous", "vous", "ils", "elles", "mais", "aussi",
    # German
    "der", "die", "das", "und", "ist", "nicht", "ein", "eine", "einer", "einem",
    "einen", "mit", "auf", "für", "von", "zu", "im", "dem", "den",
    # Turkish
    "bir", "ve", "icin", "bu", "cok", "olarak", "gibi", "ile", "daha", "kadar",
    "yeterince", "olur", "dayandin", "eylul", "ayin", "ben", "sen",
    # Portuguese
    "nao", "com", "uma", "mais", "para", "como", "dos", "das", "voce", "ele", "ela"
}


def is_english_content(
    text: str,
    declared_language: Optional[str] = None,
) -> bool:
    """Determine if text content is in English.
    
    1. If a declared language code is provided (e.g. from Mastodon or Bluesky):
       - If it starts with 'en' -> True
       - If it explicitly declares another language (e.g. 'es', 'de', 'fr', 'tr') -> False
    
    2. Check character sets and linguistic indicators:
       - Drop if non-Latin scripts (Cyrillic, Arabic, CJK, etc.) are present.
       - Drop if distinct non-English characters (¿, ¡, etc.) are present.
       - If foreign words significantly outnumber English words -> False.
       - Defaults to True for short titles or standard Latin meme text.
    """
    if declared_language:
        lang = str(declared_language).lower().strip()
        if lang.startswith("en"):
            return True
        # Explicit non-English code (e.g., 'es', 'de', 'fr', 'tr', 'ru', 'pt')
        if lang and lang not in ("und", "unknown", "zxx", "qaa"):
            return False

    if not text or not text.strip():
        return True

    # Drop non-Latin scripts
    if NON_LATIN_SCRIPT_PATTERN.search(text):
        return False

    # Drop non-English inverted question/exclamation marks or specific diacritics
    if NON_ENGLISH_CHARS_PATTERN.search(text):
        return False

    words = [w.lower() for w in re.findall(r"\b[a-zA-Z]+\b", text)]
    if not words:
        return True

    # Count foreign vs English matches
    foreign_count = sum(1 for w in words if w in FOREIGN_INDICATOR_WORDS)
    english_count = sum(1 for w in words if w in COMMON_ENGLISH_WORDS)

    if foreign_count > 0 and foreign_count >= english_count:
        return False

    return True

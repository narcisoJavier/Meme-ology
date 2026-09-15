"""Meme localization, language detection, and regional personalization engine."""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# Supported Country / Region metadata
SUPPORTED_REGIONS: Dict[str, Dict[str, str]] = {
    "GLOBAL": {"code": "GLOBAL", "name": "Global / Worldwide", "flag": "🌐", "default_lang": "en"},
    "US": {"code": "US", "name": "United States", "flag": "🇺🇸", "default_lang": "en"},
    "DE": {"code": "DE", "name": "Germany (DACH)", "flag": "🇩🇪", "default_lang": "de"},
    "FR": {"code": "FR", "name": "France", "flag": "🇫🇷", "default_lang": "fr"},
    "BR": {"code": "BR", "name": "Brazil", "flag": "🇧🇷", "default_lang": "pt"},
    "GB": {"code": "GB", "name": "United Kingdom", "flag": "🇬🇧", "default_lang": "en"},
    "ES": {"code": "ES", "name": "Spain / LatAm", "flag": "🇪🇸", "default_lang": "es"},
    "JP": {"code": "JP", "name": "Japan", "flag": "🇯🇵", "default_lang": "ja"},
}

# Subreddit / Community to (country_code, language)
COMMUNITY_LOCATION_MAP: Dict[str, Tuple[str, str]] = {
    "ich_iel": ("DE", "de"),
    "r/ich_iel": ("DE", "de"),
    "de": ("DE", "de"),
    "r/de": ("DE", "de"),
    "rance": ("FR", "fr"),
    "r/rance": ("FR", "fr"),
    "france": ("FR", "fr"),
    "r/france": ("FR", "fr"),
    "eu_nvr": ("BR", "pt"),
    "r/eu_nvr": ("BR", "pt"),
    "brasil": ("BR", "pt"),
    "r/brasil": ("BR", "pt"),
    "yo_elvr": ("ES", "es"),
    "r/yo_elvr": ("ES", "es"),
    "dankmemes": ("US", "en"),
    "r/dankmemes": ("US", "en"),
    "memes": ("GLOBAL", "en"),
    "r/memes": ("GLOBAL", "en"),
    "me_irl": ("GLOBAL", "en"),
    "r/me_irl": ("GLOBAL", "en"),
    "genalpha": ("US", "en"),
    "r/genalpha": ("US", "en"),
    "wholesomememes": ("GLOBAL", "en"),
    "r/wholesomememes": ("GLOBAL", "en"),
    "adviceanimals": ("US", "en"),
    "r/adviceanimals": ("US", "en"),
}

# Lexical patterns for heuristic language and region detection
GERMAN_WORDS = {
    "der", "die", "das", "und", "ist", "nicht", "ein", "eine", "einer", "einem",
    "einen", "mit", "auf", "für", "von", "zu", "im", "dem", "den", "ich_iel",
    "gepostet", "von", "jäger", "erschießt", "warum", "wenn", "aber", "alle",
    "rhein", "tiere", "menschen", "unterscheidet", "redewendung"
}

FRENCH_WORDS = {
    "le", "la", "les", "des", "du", "dans", "avec", "pour", "est", "sont", "cette",
    "cet", "nous", "vous", "ils", "elles", "mais", "aussi", "qu'on", "disent",
    "baiser", "cerveau", "plaisir", "donne", "envie", "automobilistes", "cycliste",
    "feu", "rouge", "radar", "travaux", "faute", "chasseur", "saison", "victimes"
}

PORTUGUESE_WORDS = {
    "não", "com", "uma", "mais", "para", "como", "dos", "das", "você", "ele",
    "ela", "hoje", "igual", "torresmo", "pastelzao", "preciso", "bicho",
    "vamos", "exercitar", "tô", "pariu", "henrique"
}

SPANISH_WORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "en", "que",
    "por", "para", "con", "del", "al", "pero", "como", "más", "aquí", "está",
    "este", "usted", "tiempo", "ahora", "todos", "cuando", "donde"
}


def detect_language_from_text(text: str) -> str:
    """Infer language code ('en', 'de', 'fr', 'pt', 'es') from text tokens."""
    if not text or not text.strip():
        return "en"

    # Tokenize lowercase words
    words = set(re.findall(r"\b[a-zA-Záéíóúâêîôûãõàèìòùäöüßç]+\b", text.lower()))
    if not words:
        return "en"

    de_count = len(words.intersection(GERMAN_WORDS))
    fr_count = len(words.intersection(FRENCH_WORDS))
    pt_count = len(words.intersection(PORTUGUESE_WORDS))
    es_count = len(words.intersection(SPANISH_WORDS))

    counts = [("de", de_count), ("fr", fr_count), ("pt", pt_count), ("es", es_count)]
    counts.sort(key=lambda x: x[1], reverse=True)

    best_lang, best_count = counts[0]
    if best_count >= 2:
        return best_lang

    return "en"


def detect_meme_location(
    title: str,
    source_community: Optional[str] = None,
    source_platform: Optional[str] = None,
    author: Optional[str] = None,
) -> Tuple[str, str]:
    """Determine (country_code, language) for a meme based on community, author, and text.
    
    Returns:
        Tuple of (country_code, language_code) e.g. ('DE', 'de'), ('US', 'en'), ('GLOBAL', 'en').
    """
    comm = (source_community or "").lower().strip()
    auth = (author or "").lower().strip()
    clean_comm = comm.lstrip("r/").lstrip("#").strip()

    # Direct community map
    if clean_comm in COMMUNITY_LOCATION_MAP:
        return COMMUNITY_LOCATION_MAP[clean_comm]
    if comm in COMMUNITY_LOCATION_MAP:
        return COMMUNITY_LOCATION_MAP[comm]

    # Domain / instance TLD clues from author or community
    if auth.endswith(".de") or "ich-iel" in auth:
        return "DE", "de"
    if auth.endswith(".fr") or ".fr." in auth:
        return "FR", "fr"
    if auth.endswith(".br") or ".br." in auth:
        return "BR", "pt"
    if auth.endswith(".es") or ".es." in auth:
        return "ES", "es"
    if auth.endswith(".jp") or ".jp." in auth:
        return "JP", "ja"
    if auth.endswith(".uk") or ".co.uk" in auth:
        return "GB", "en"

    # Detect from text content
    detected_lang = detect_language_from_text(title)
    if detected_lang == "de":
        return "DE", "de"
    if detected_lang == "fr":
        return "FR", "fr"
    if detected_lang == "pt":
        return "BR", "pt"
    if detected_lang == "es":
        return "ES", "es"

    # Default to Global English
    return "GLOBAL", "en"


def get_country_metadata(code: str) -> Dict[str, str]:
    """Retrieve metadata dictionary (name, flag, default_lang) for a country code."""
    upper = (code or "GLOBAL").upper().strip()
    return SUPPORTED_REGIONS.get(upper, SUPPORTED_REGIONS["GLOBAL"])

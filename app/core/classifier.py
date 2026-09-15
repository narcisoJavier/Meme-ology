"""Generational meme classification and authenticity validation engine."""

from __future__ import annotations

import re
from typing import Optional

# Keywords and patterns associated with internet culture generations
GEN_ALPHA_PATTERNS = [
    r"\bskibidi\b",
    r"\btoilet\b",
    r"\bohio\b",
    r"\brizz(ler)?\b",
    r"\bfanum(\s+tax)?\b",
    r"\bsigma\b",
    r"\bmew(ing)?\b",
    r"\bgyatt\b",
    r"\bkai\s+cenat\b",
    r"\bbaby\s+gronk\b",
    r"\bgrimace(\s+shake)?\b",
    r"\bbrainrot\b",
    r"\bcaseoh\b",
    r"\bsmurf\s+cat\b",
    r"\bedging\b",
    r"\blooksmax(xing)?\b",
    r"\blopunny\b",
]

GEN_Z_PATTERNS = [
    r"\bwojak\b",
    r"\b(giga)?chad\b",
    r"\bnpc\b",
    r"\bbarbenheimer\b",
    r"\bgoofy\s+ahh\b",
    r"\bbruh\b",
    r"\byeet\b",
    r"\bno\s+cap\b",
    r"\bbussin\b",
    r"\bsheesh\b",
    r"\bfr\s+fr\b",
    r"\bratio\b",
    r"\bong\b",
    r"\bdeep\s+fried\b",
    r"\bsurreal\b",
    r"\bdank\b",
    r"\btiktok\b",
    r"\bphonk\b",
    r"\bamogus\b",
    r"\bsus\b",
    r"\bquandale\b",
]

MILLENNIAL_PATTERNS = [
    r"\bdoge\b",
    r"\bdistracted(\s+boyfriend)?\b",
    r"\bdrake(\s+hotline)?\b",
    r"\bbad\s+luck\s+brian\b",
    r"\bsuccess\s+kid\b",
    r"\bgrumpy\s+cat\b",
    r"\broll\s+safe\b",
    r"\bgalaxy\s+brain\b",
    r"\bpepe\b",
    r"\brage\s+comic\b",
    r"\btrollface\b",
    r"\bscumbag\s+steve\b",
    r"\boverly\s+attached\b",
    r"\bwoman\s+yelling\b",
    r"\badulting\b",
    r"\bphilosoraptor\b",
    r"\bfirst\s+world\s+problems\b",
]

GEN_X_BOOMER_PATTERNS = [
    r"\bminion(s)?\b",
    r"\blolcat(s)?\b",
    r"\bcheezburger\b",
    r"\b(i\s+can\s+haz\s+)?cheezburger\b",
    r"\bdancing\s+baby\b",
    r"\bdemotivational\b",
    r"\ball\s+your\s+base\b",
    r"\bboomer\b",
    r"\bfacebook\b",
    r"\bforward(ed)?\b",
    r"\bback\s+in\s+my\s+day\b",
    r"\bkids\s+these\s+days\b",
    r"\bphone\s+bad\b",
    r"\bbook\s+good\b",
]

# Compile patterns for performance
RE_GEN_ALPHA = re.compile("|".join(GEN_ALPHA_PATTERNS), re.IGNORECASE)
RE_GEN_Z = re.compile("|".join(GEN_Z_PATTERNS), re.IGNORECASE)
RE_MILLENNIAL = re.compile("|".join(MILLENNIAL_PATTERNS), re.IGNORECASE)
RE_GEN_X = re.compile("|".join(GEN_X_BOOMER_PATTERNS), re.IGNORECASE)

# Patterns for non-meme false positives
RE_FRENCH_HOMOGRAPH = re.compile(
    r"\b(quand\s+m[eê]me|tout\s+de\s+m[eê]me|m[eê]me\s+si|le\s+m[eê]me\s+pour|de\s+m[eê]me)\b",
    re.IGNORECASE,
)
RE_MEME_INTENT = re.compile(
    r"\b(meme|memes|humour|shitpost|shitposting|lmao|funny|dank|joke|satire|pov)\b|#\w*meme\w*",
    re.IGNORECASE,
)
RE_SPAM_OR_PROMO = re.compile(
    r"\b(totagoal\.com|funhouseradio\.com|tunein\.com|affiliate|subscribe\s+to\s+my)\b",
    re.IGNORECASE,
)
RE_OBITUARY_HOAX = re.compile(
    r"\b(lost\s+a\s+trailblazer|rest\s+in\s+peace|r\.?i\.?p\.?|sad\s+news\.\.\.|tue\s+un\s+autre\s+chasseur|gloria\s+steinem)\b",
    re.IGNORECASE,
)


def classify_meme_generation(
    title: str,
    source_community: Optional[str] = None,
    source_platform: Optional[str] = None,
) -> str:
    """Classify a meme into its cultural generation based on lexical indicators and community."""
    text = (title or "").lower()
    community = (source_community or "").lower()

    # Explicit community mapping overrides
    if "genalpha" in community or "skibiditoilet" in community:
        return "gen_alpha"
    if "genz" in community:
        return "gen_z"
    if "adviceanimals" in community or "millennial" in community:
        return "millennial"
    if "boomer" in community or "facebook" in community:
        return "gen_x"

    # Text pattern evaluation (ordered by modern specificity)
    if RE_GEN_ALPHA.search(text):
        return "gen_alpha"
    if RE_GEN_Z.search(text):
        return "gen_z"
    if RE_MILLENNIAL.search(text):
        return "millennial"
    if RE_GEN_X.search(text):
        return "gen_x"

    # Secondary community defaults
    if "wholesomememes" in community:
        return "gen_x"
    if "me_irl" in community or "dankmemes" in community:
        return "gen_z"
    if "memes" in community:
        return "gen_z"

    return "gen_z"


def is_valid_meme_content(
    title: str,
    media_url: str = "",
    author: str = "",
    source_community: Optional[str] = None,
) -> bool:
    """Validate that ingested content is authentic meme material and not false positive/spam."""
    clean_title = (title or "").strip()
    clean_url = (media_url or "").strip()
    clean_comm = (source_community or "").lower()

    # Reddit meme communities and Know Your Meme entries are trusted by default
    if clean_comm.startswith("r/") or "knowyourmeme" in clean_comm or clean_comm in ("confirmed", "trending"):
        return True

    # Reject promotional spam domains
    if RE_SPAM_OR_PROMO.search(clean_title) or RE_SPAM_OR_PROMO.search(clean_url):
        return False

    # Reject serious death / obituary hoaxes unless marked satire
    if RE_OBITUARY_HOAX.search(clean_title) and not re.search(r"\b(satire|parody|meme)\b", clean_title, re.I):
        return False

    # Reject French homographs where "même" was matched as a regular adverb/adjective
    if RE_FRENCH_HOMOGRAPH.search(clean_title):
        # Only accept if there is explicit meme context or hashtag
        has_explicit_meme = bool(RE_MEME_INTENT.search(clean_title))
        # If title only matched "quand même" or "le même pour tous" without meme hashtags, reject
        clean_no_homo = RE_FRENCH_HOMOGRAPH.sub("", clean_title)
        if not RE_MEME_INTENT.search(clean_no_homo):
            return False

    return True

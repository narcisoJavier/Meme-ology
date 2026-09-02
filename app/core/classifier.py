"""Generational meme classification and taxonomy engine."""

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
        # Balanced general memes default to gen_z
        return "gen_z"

    return "gen_z"

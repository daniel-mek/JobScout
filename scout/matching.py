"""Decide what a listing is: which company tier, which role, where, and whether it is freshman-friendly.

Everything here reads config/targets.yaml and returns plain strings, so scoring.py can turn
the answers into points and the breakdown can show a human why.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent
TARGETS_PATH = ROOT / "config" / "targets.yaml"

# Short words that must match whole words only. "it" inside "Pittsburgh" is not an IT job.
SHORT_TOKENS = {"it", "ui", "ux", "swe", "sde", "pm", "apm", "ai", "ml", "web", "ios", "nj", "ny", "nyc", "uk", "aws", "ibm", "x", "step", "rf"}

US_STATES = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me",
    "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa",
    "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc",
}
US_CITY_SHORTHANDS = {"nyc", "sf", "la", "usa", "united states", "us"}


def load_targets(path: Path = TARGETS_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _word_match(text: str, word: str) -> bool:
    """True when `word` appears in `text`. Short tokens and single words match on word boundaries."""
    word = word.lower().strip()
    if not word:
        return False
    if word in SHORT_TOKENS or (" " not in word and len(word) <= 4):
        return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text) is not None
    return word in text


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


# ---------------------------------------------------------------- company tier

CORPORATE_SUFFIXES = ("inc", "llc", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "lp", "l p", "holdings", "group")


def _company_core(company: str) -> str:
    """'Apple Inc.' -> 'apple', 'NVIDIA Corporation' -> 'nvidia', 'Apple Bank' -> 'apple bank' (unchanged)."""
    name = re.sub(r"[^a-z0-9 ]+", " ", _clean(company).replace(".", ""))  # "L.P." -> "lp", "Inc." -> "inc"
    name = re.sub(r"\s+", " ", name).strip()
    words = name.split(" ")
    while len(words) > 1 and words[-1] in CORPORATE_SUFFIXES:
        words.pop()
    return " ".join(words)


def company_tier(company: str, targets: dict) -> tuple[int, str | None]:
    """('Google LLC') -> (1, 'google'). Anything not listed -> (3, None).

    The whole company name (minus Inc/LLC/Corp) must equal an alias. A word match is not enough:
    "Apple Bank" is not Apple and "Meta Marketing Group" is not Meta. Subsidiaries that should count
    (Amazon Web Services, Google DeepMind) are listed as their own alias in targets.yaml.
    """
    core = _company_core(company)
    if not core:
        return 3, None
    for tier_number, group in ((1, targets.get("tier1", {})), (2, targets.get("tier2", {}))):
        for canonical, aliases in group.items():
            if any(core == _company_core(alias) for alias in aliases):
                return tier_number, canonical
    return 3, None


# ---------------------------------------------------------------- role

def classify_role(title: str, targets: dict) -> str:
    """Return 'swe' | 'pm' | 'it' | 'design' | 'none' from the title."""
    text = _clean(title)
    roles = targets["roles"]
    if any(_word_match(text, w) for w in roles.get("exclude", [])):
        return "none"
    for role in ("design", "pm", "it", "swe"):
        if any(_word_match(text, w) for w in roles.get(role, [])):
            return role
    return "none"


# ---------------------------------------------------------------- early career

def early_career(title: str, company_key: str | None, targets: dict, url: str = "") -> str:
    """Return 'strong' (freshman/sophomore word or a named program), 'weak' ('early career'), or 'none'.

    The URL is searched too, because the lists often shorten titles: NVIDIA's Ignite posting is listed
    as "Software Engineer Intern" while its URL says "NVIDIA-2027-Ignite-Internships".
    """
    path = re.sub(r"[-_/+.%]+", " ", urlsplit(url).path.lower()) if url else ""
    text = _clean(title) + " " + path
    programs = targets.get("programs", {})
    if company_key and any(_word_match(text, w) for w in programs.get(company_key, [])):
        return "strong"
    if any(_word_match(text, w) for w in programs.get("any", [])):
        return "strong"
    if any(_word_match(text, w) for w in targets.get("early_career_weak", [])):
        return "weak"
    return "none"


# ---------------------------------------------------------------- location

def location_class(locations: list[str], targets: dict) -> str:
    """Best location in the list: 'priority' (NJ, NYC, remote US) | 'us' | 'other' | 'unknown'."""
    if not locations:
        return "unknown"
    cfg = targets["locations"]
    best = "other"
    for raw in locations:
        loc = _clean(raw)
        if any(_word_match(loc, w) for w in cfg.get("non_us_words", [])):
            continue  # a non-US location can never raise the class
        if any(_word_match(loc, w) for w in cfg.get("priority", [])):
            return "priority"
        if any(_word_match(loc, w) for w in cfg.get("remote_words", [])):
            return "priority"  # bare "Remote" with no other country named
        if _looks_us(loc):
            best = "us"
    return best


def _looks_us(loc: str) -> bool:
    if loc in US_CITY_SHORTHANDS or any(_word_match(loc, w) for w in ("united states", "usa")):
        return True
    tail = loc.rsplit(",", 1)[-1].strip()
    return tail in US_STATES


# ---------------------------------------------------------------- degrees

def degree_class(degrees: list[str], targets: dict) -> str:
    """'bachelors' | 'unknown' | 'graduate_only'."""
    if not degrees:
        return "unknown"
    graduate_only = {d.lower() for d in targets.get("graduate_only_degrees", [])}
    listed = {d.lower() for d in degrees}
    if listed and listed <= graduate_only:
        return "graduate_only"
    return "bachelors"


# ---------------------------------------------------------------- keywords

def keyword_hits(title: str, targets: dict) -> list[str]:
    text = _clean(title)
    return [k for k in targets.get("keywords", []) if _word_match(text, k)]


# ---------------------------------------------------------------- put it together

def describe(listing: dict, targets: dict) -> dict:
    """Attach tier, role, early-career, location, degree, and keyword facts to a listing (in place)."""
    tier, company_key = company_tier(listing["company"], targets)
    listing["tier"] = tier
    listing["company_key"] = company_key
    listing["role"] = classify_role(listing["title"], targets)
    listing["early_career"] = early_career(listing["title"], company_key, targets, listing.get("url", ""))
    listing["location_class"] = location_class(listing.get("locations", []), targets)
    listing["degree_class"] = degree_class(listing.get("degrees", []), targets)
    listing["keyword_hits"] = keyword_hits(listing["title"], targets)
    return listing


def passes_filters(listing: dict, cycle_year: str = "2027", max_age_days: int | None = None,
                   now: float | None = None) -> tuple[bool, str]:
    """Hard drops only. Returns (keep, reason). Everything that passes gets scored, nothing is hidden for location."""
    if not listing.get("active", True):
        return False, "inactive"
    if not any(cycle_year in t for t in listing.get("terms", [])):
        return False, "not a 2027 term"
    if max_age_days and listing.get("date_posted"):
        import time
        age_days = ((now if now is not None else time.time()) - listing["date_posted"]) / 86400
        if age_days > max_age_days:
            return False, f"older than {max_age_days} days"
    if listing.get("degree_class") == "graduate_only":
        return False, "graduate students only"
    if listing.get("role") == "none" and listing.get("early_career") != "strong":
        return False, "not a target role"
    return True, "ok"

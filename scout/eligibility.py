"""Read a posting page and look for a graduation-year requirement.

Many postings say things like "graduating between December 2027 and June 2028" or "Class of 2028".
For someone graduating in 2030 (graduation_year in config/targets.yaml) those are out even when the
list says "Bachelor's". The lists
do not carry this, so for the top matches Scout fetches the page (only on plain-HTML boards:
Greenhouse, Lever, Ashby) and reads it.

Verdicts:
  "ok"          the page names a year range that includes your graduation year, or says freshman/sophomore
  "ineligible"  the page names graduation years and yours is not among them, or asks for penultimate-year,
                final-year, junior, or senior students
  "unknown"     the page could not be read, or says nothing about graduation year (never hidden, just labeled)

Reading the page is scout/posting.py's job (Workday, Google Careers, Greenhouse, Lever, Ashby).

Results are cached in data/eligibility_cache.json by URL so a page is fetched once, not every run.
Posting text is untrusted: it is only ever searched with regular expressions, never executed or followed.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from scout import posting

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "eligibility_cache.json"
CACHE_DAYS = 14

_TAGS = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S | re.I)
_YEAR = re.compile(r"\b(20[2-3][0-9])\b")
# A graduation requirement is a sentence with "graduat..." or "class of" in it. Every year in that
# sentence counts, so "December 2028, May 2029, December 2029, or May 2030" yields all four.
_GRAD_SENTENCE = re.compile(r"[^.\n]{0,80}\b(?:graduat\w*|class of)\b[^.\n]{0,160}", re.I)
_UNDERCLASS = re.compile(r"\b(freshman|freshmen|sophomore|first[- ]year|second[- ]year|underclass\w*)\b", re.I)
# Phrases that mean "not a freshman": Google writes "penultimate academic year", others say "rising junior".
_UPPERCLASS = re.compile(
    r"\b(penultimate|final[- ]year|last[- ]year of|rising (?:junior|senior)s?|junior or senior|juniors and seniors|"
    r"junior/senior|third[- ]year or fourth[- ]year|(?:junior|senior) standing)\b", re.I)


def is_readable_board(url: str) -> bool:
    return posting.is_readable_board(url)


def fetch_text(url: str) -> str | None:
    """The posting's text, or None when the board cannot be read server-side."""
    post = posting.read_posting(url)
    return post["text"] if post else None


def years_mentioned(text: str) -> list[int]:
    """Every graduation year the page names, e.g. 'graduating between Dec 2027 and June 2028' -> [2027, 2028]."""
    years: set[int] = set()
    for sentence in _GRAD_SENTENCE.finditer(text):
        for year in _YEAR.findall(sentence.group(0)):
            years.add(int(year))
    return sorted(years)


def verdict_from_text(text: str, graduation_year: int) -> tuple[str, str]:
    """('ok' | 'ineligible' | 'unknown', short reason)."""
    years = years_mentioned(text)
    if _UNDERCLASS.search(text):
        return "ok", "page mentions freshman/sophomore/underclassmen"
    upper = _UPPERCLASS.search(text)
    if upper and not years:
        return "ineligible", f"page asks for {upper.group(1).lower()} students"
    if not years:
        return "unknown", "page says nothing about graduation year"
    low, high = min(years), max(years)
    if low <= graduation_year <= high:
        return "ok", f"page names graduation {low}" + (f" to {high}" if high != low else "")
    return "ineligible", f"page requires graduation {low}" + (f" to {high}" if high != low else "")


def load_cache(path: Path = CACHE_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(cache: dict, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")


def check(listing: dict, graduation_year: int, cache: dict, allow_network: bool = True) -> dict:
    """Attach 'eligibility' and 'eligibility_note' to a listing. Uses the cache first, then the network."""
    url = listing.get("url", "")
    cached = cache.get(url)
    if cached and time.time() - cached.get("checked_at", 0) < CACHE_DAYS * 24 * 3600:
        listing["eligibility"], listing["eligibility_note"] = cached["verdict"], cached["note"]
        return listing
    if not allow_network or not is_readable_board(url):
        listing["eligibility"], listing["eligibility_note"] = "unknown", "not checked (board can't be read server-side)" if not is_readable_board(url) else "not checked (network off)"
        return listing
    text = fetch_text(url)
    if text is None:
        verdict, note = "unknown", "page could not be read"
    else:
        verdict, note = verdict_from_text(text, graduation_year)
    cache[url] = {"verdict": verdict, "note": note, "checked_at": int(time.time())}
    listing["eligibility"], listing["eligibility_note"] = verdict, note
    return listing

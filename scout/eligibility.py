"""Read a posting page and look for a graduation-year requirement.

Many postings say things like "graduating between December 2027 and June 2028" or "Class of 2028".
Jeremiah graduates in 2030, so those are out even when the list says "Bachelor's". The lists
do not carry this, so for the top matches Scout fetches the page (only on plain-HTML boards:
Greenhouse, Lever, Ashby) and reads it.

Verdicts:
  "ok"          the page names a year range that includes his graduation year, or says freshman/sophomore
  "ineligible"  the page names graduation years and his is not among them
  "unknown"     the page could not be read, or says nothing about graduation year (never hidden, just labeled)

Results are cached in data/eligibility_cache.json by URL so a page is fetched once, not every run.
Posting text is untrusted: it is only ever searched with regular expressions, never executed or followed.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "eligibility_cache.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) scout-internship-watcher/0.1"
CACHE_DAYS = 14

# Only boards that serve the posting as plain HTML. Everything else (Workday, custom sites) stays "unknown".
PLAIN_HTML_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com")

_TAGS = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S | re.I)
_YEAR = r"(20[2-3][0-9])"
# Phrases that introduce a graduation requirement, followed within a few words by one or two years.
_GRAD_PATTERNS = [
    re.compile(rf"graduat\w*[^.\n]{{0,60}}?{_YEAR}(?:[^.\n]{{0,25}}?{_YEAR})?", re.I),
    re.compile(rf"class of[^.\n]{{0,10}}?{_YEAR}(?:[^.\n]{{0,15}}?{_YEAR})?", re.I),
    re.compile(rf"{_YEAR}(?:\s*(?:-|to|or|and|/)\s*{_YEAR})?\s+graduat", re.I),
]
_UNDERCLASS = re.compile(r"\b(freshman|freshmen|sophomore|first[- ]year|second[- ]year|underclass\w*)\b", re.I)


def is_plain_html_board(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return any(host == h or host.endswith("." + h) for h in PLAIN_HTML_HOSTS)


def fetch_text(url: str, timeout: int = 15) -> str | None:
    """Download the page and strip it to text. Returns None when it cannot be read."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(2_000_000).decode("utf-8", errors="replace")
    except Exception:
        return None
    return html.unescape(_TAGS.sub(" ", raw))


def years_mentioned(text: str) -> list[int]:
    """Every graduation year the page names, e.g. 'graduating between Dec 2027 and June 2028' -> [2027, 2028]."""
    years: set[int] = set()
    for pattern in _GRAD_PATTERNS:
        for match in pattern.finditer(text):
            for group in match.groups():
                if group:
                    years.add(int(group))
    return sorted(years)


def verdict_from_text(text: str, graduation_year: int) -> tuple[str, str]:
    """('ok' | 'ineligible' | 'unknown', short reason)."""
    years = years_mentioned(text)
    if _UNDERCLASS.search(text):
        return "ok", "page mentions freshman/sophomore/underclassmen"
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
    if not allow_network or not is_plain_html_board(url):
        listing["eligibility"], listing["eligibility_note"] = "unknown", "not checked (not a plain-HTML board)" if not is_plain_html_board(url) else "not checked (network off)"
        return listing
    text = fetch_text(url)
    if text is None:
        verdict, note = "unknown", "page could not be read"
    else:
        verdict, note = verdict_from_text(text, graduation_year)
    cache[url] = {"verdict": verdict, "note": note, "checked_at": int(time.time())}
    listing["eligibility"], listing["eligibility_note"] = verdict, note
    return listing

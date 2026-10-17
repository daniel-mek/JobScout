"""Check whether a posting is closed, caching availability by URL.

An open page does not establish personal eligibility; applicants review its requirements.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from scout import posting

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "eligibility_cache.json"
CACHE_DAYS = 14
CLOSED = "\0closed"  # fetch_text's answer for a posting the board says is gone
CACHE_VERSION = 6  # bump when the verdict rules change, so old verdicts are re-read

def is_readable_board(url: str) -> bool:
    return posting.is_readable_board(url)


def fetch_text(url: str) -> str | None:
    """The posting's text, CLOSED when the board says it is gone, or None when it cannot be read server-side."""
    post = posting.read_posting(url)
    if post and post.get("closed"):
        return CLOSED
    return post["text"] if post else None


def load_cache(path: Path = CACHE_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(cache: dict, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")


def check(listing: dict, cache: dict, allow_network: bool = True) -> dict:
    """Attach 'eligibility' and 'eligibility_note' to a listing. Uses the cache first, then the network."""
    url = listing.get("url", "")
    cache_key = url
    cached = cache.get(cache_key)
    if cached and cached.get("v") == CACHE_VERSION and time.time() - cached.get("checked_at", 0) < CACHE_DAYS * 24 * 3600:
        listing["eligibility"], listing["eligibility_note"] = cached["verdict"], cached["note"]
        return listing
    if not allow_network or not is_readable_board(url):
        listing["eligibility"], listing["eligibility_note"] = "unknown", "not checked (board can't be read server-side)" if not is_readable_board(url) else "not checked (network off)"
        return listing
    text = fetch_text(url)
    if text is None:
        # Not cached: one timeout should not lock a Tier 1 posting at "unknown" for two weeks.
        listing["eligibility"], listing["eligibility_note"] = "unknown", "page could not be read"
        return listing
    if text == CLOSED:
        verdict, note = "closed", "the posting has been taken down"
    else:
        verdict, note = "unknown", "posting available; review experience, skills, and work authorization requirements"
    cache[cache_key] = {"verdict": verdict, "note": note, "checked_at": int(time.time()), "v": CACHE_VERSION}
    listing["eligibility"], listing["eligibility_note"] = verdict, note
    return listing


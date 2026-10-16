"""Decide which matches get an instant push and which wait for the 7:00 PM digest.

Instant (every run): Tier 1 or Tier 2 at or above `instant_min_score`, any freshman/sophomore program,
any ambassador program. Everything else that passed the filters goes into the daily digest, top N by score.
data/seen.json remembers every key that has been alerted, with its URLs, so nothing alerts twice
but a repost under a reused title still does.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEN_PATH = ROOT / "data" / "seen.json"
RULED_OUT = ("ineligible", "closed")  # the posting page itself says he can't apply


def load_seen(path: Path = SEEN_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_seen(seen: dict, path: Path = SEEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(seen, indent=1, sort_keys=True), encoding="utf-8")


def is_instant(m: dict, weights: dict) -> bool:
    if m.get("eligibility") in RULED_OUT:
        return False
    if m.get("early_career") == "strong" or m.get("role") == "ambassador":
        return True
    return m.get("tier", 3) <= 2 and m.get("score", 0) >= weights.get("instant_min_score", 60)


def is_new(m: dict, seen: dict) -> bool:
    """Never alerted, or a repost: same company and title, but a URL we have not alerted and a post date
    after the last alert. Big tech reuses titles like "Software Engineer Intern" for every new team and season.
    """
    entry = seen.get(m["key"])
    if entry is None:
        return True
    if set(m.get("urls") or [m.get("url")]) & set(entry.get("urls", [])):
        return False
    try:
        last = datetime.fromisoformat(entry["at"]).timestamp()
    except (KeyError, ValueError):
        return False
    return (m.get("latest_posted") or m.get("date_posted") or 0) > last


def select_instant(matches: list[dict], seen: dict, weights: dict) -> list[dict]:
    return [m for m in matches if is_new(m, seen) and is_instant(m, weights)]


def select_digest(matches: list[dict], seen: dict, weights: dict) -> list[dict]:
    """Top N unseen matches above the floor, instant ones excluded (they already pushed)."""
    floor = weights.get("min_score", 30)
    size = weights.get("digest_size", 10)
    pool = [m for m in matches if is_new(m, seen) and m.get("score", 0) >= floor
            and m.get("eligibility") not in RULED_OUT and not is_instant(m, weights)]
    return pool[:size]


def mark_seen(seen: dict, items: list[dict], channel: str, now: float | None = None) -> None:
    stamp = datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc).isoformat(timespec="seconds")
    for m in items:
        urls = sorted(set((seen.get(m["key"]) or {}).get("urls", [])) | set(m.get("urls") or []))
        seen[m["key"]] = {"at": stamp, "via": channel, "company": m["company"], "title": m["title"],
                          "score": m["score"], "urls": urls}

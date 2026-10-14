"""Decide which matches get an instant push and which wait for the 7:00 PM digest.

Instant (every run): Tier 1 or Tier 2 at or above `instant_min_score`, any freshman/sophomore program,
any ambassador program. Everything else that passed the filters goes into the daily digest, top N by score.
data/seen.json remembers every key that has been alerted, so nothing alerts twice.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEN_PATH = ROOT / "data" / "seen.json"


def load_seen(path: Path = SEEN_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_seen(seen: dict, path: Path = SEEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(seen, indent=1, sort_keys=True), encoding="utf-8")


def is_instant(m: dict, weights: dict) -> bool:
    if m.get("eligibility") == "ineligible":
        return False
    if m.get("early_career") == "strong" or m.get("role") == "ambassador":
        return True
    return m.get("tier", 3) <= 2 and m.get("score", 0) >= weights.get("instant_min_score", 60)


def select_instant(matches: list[dict], seen: dict, weights: dict) -> list[dict]:
    return [m for m in matches if m["key"] not in seen and is_instant(m, weights)]


def select_digest(matches: list[dict], seen: dict, weights: dict) -> list[dict]:
    """Top N unseen matches above the floor, instant ones excluded (they already pushed)."""
    floor = weights.get("min_score", 30)
    size = weights.get("digest_size", 10)
    pool = [m for m in matches if m["key"] not in seen and m.get("score", 0) >= floor
            and m.get("eligibility") != "ineligible" and not is_instant(m, weights)]
    return pool[:size]


def mark_seen(seen: dict, items: list[dict], channel: str, now: float | None = None) -> None:
    stamp = datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc).isoformat(timespec="seconds")
    for m in items:
        seen[m["key"]] = {"at": stamp, "via": channel, "company": m["company"], "title": m["title"], "score": m["score"]}

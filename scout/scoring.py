"""Turn the facts from matching.py into a 0 to 100 score, with a breakdown that explains every point.

Weights come from config/scoring.yaml. The breakdown is a dict like
  {"role": 30, "tier": 20, "early_career": 0, "degrees": 5, "location": 15, "freshness": 10, "keywords": 3}
and score == min(100, sum(breakdown.values())).
"""

from __future__ import annotations

import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCORING_PATH = ROOT / "config" / "scoring.yaml"

DAY = 24 * 60 * 60


def load_weights(path: Path = SCORING_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def freshness_class(date_posted: int, now: float | None = None) -> str:
    now = now if now is not None else time.time()
    age = now - (date_posted or 0)
    if date_posted and age < DAY:
        return "under_24h"
    if date_posted and age < 7 * DAY:
        return "under_7d"
    if date_posted and age > 90 * DAY:
        return "over_90d"
    return "older"


def score(listing: dict, weights: dict, now: float | None = None) -> dict:
    """Attach 'score' and 'breakdown' to a described listing (in place) and return it."""
    w = weights
    loc = listing.get("location_class", "unknown")
    role = listing.get("role", "none")
    if role == "none" and listing.get("early_career") == "strong":
        role = "program"  # "Explore Program" names no role but is exactly what a freshman wants
        listing["role"] = role
    fresh = freshness_class(listing.get("date_posted", 0), now)
    if fresh == "over_90d" and listing.get("tier", 3) in w.get("no_stale_penalty_tiers", []):
        fresh = "older"
    breakdown = {
        "role": w["role"].get(role, 0),
        "tier": w["tier"].get(listing.get("tier", 3), 0),
        "early_career": w["early_career"].get(listing.get("early_career", "none"), 0),
        "degrees": w["degrees"]["bachelors_listed"] if listing.get("degree_class") == "bachelors" else w["degrees"]["unknown"],
        "location": w["location"].get("priority" if loc == "priority" else "us" if loc == "us" else "other", 0),
        "freshness": w["freshness"].get(fresh, 0),
        "keywords": min(w["keywords"]["max"], w["keywords"]["per_hit"] * len(listing.get("keyword_hits", []))),
    }
    listing["breakdown"] = breakdown
    listing["score"] = min(100, sum(breakdown.values()))
    return listing


def explain(listing: dict) -> str:
    """One line a human can read: 'role swe 30 + tier 1 20 + early none 0 + deg 5 + loc priority 15 + fresh 10 + kw 3 = 83'."""
    b = listing["breakdown"]
    return (
        f"role {listing.get('role')} {b['role']} + tier {listing.get('tier')} {b['tier']} + "
        f"early {listing.get('early_career')} {b['early_career']} + deg {b['degrees']} + "
        f"loc {listing.get('location_class')} {b['location']} + fresh {b['freshness']} + "
        f"kw {b['keywords']} = {listing['score']}"
    )

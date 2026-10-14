"""The application tracker, as a file: data/tracker.json.

States, in order: Found, Saved, Prepped, Applied, OA, Interview, Offer, Rejected, Withdrawn.
M5 mirrors this into Workers KV so it can be updated from the phone; until then this file is the truth.

    .venv/bin/python -m scout.tracker set <key> <state> [--note "..."] [--next "..."]
    .venv/bin/python -m scout.tracker list
    .venv/bin/python -m scout.tracker show <key>

The tracker holds company, title, url, score, state, dates, and a next action. Nothing personal.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKER_PATH = ROOT / "data" / "tracker.json"
MATCHES_PATH = ROOT / "data" / "matches.json"

STATES = ["Found", "Saved", "Prepped", "Applied", "OA", "Interview", "Offer", "Rejected", "Withdrawn"]


def load(path: Path = TRACKER_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(tracker: dict, path: Path = TRACKER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(tracker, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def find_match(key: str, matches_path: Path = MATCHES_PATH) -> dict | None:
    try:
        data = json.loads(Path(matches_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return next((m for m in data.get("matches", []) if m.get("key") == key), None)


def set_state(tracker: dict, key: str, state: str, note: str = "", next_action: str = "",
              match: dict | None = None, today: str | None = None) -> dict:
    """Move one posting to a state. Creates the row from the match (or a bare row) when new."""
    if state not in STATES:
        raise ValueError(f"unknown state {state!r}; use one of {', '.join(STATES)}")
    today = today or date.today().isoformat()
    row = tracker.get(key) or {
        "company": (match or {}).get("company", ""),
        "title": (match or {}).get("title", ""),
        "url": (match or {}).get("url", ""),
        "score": (match or {}).get("score"),
        "history": [],
    }
    row["state"] = state
    row["updated"] = today
    if state == "Applied" and not row.get("applied"):
        row["applied"] = today
    if next_action:
        row["next"] = next_action
    if note:
        row.setdefault("notes", []).append(f"{today}: {note}")
    row["history"].append({"date": today, "state": state})
    tracker[key] = row
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set")
    s.add_argument("key")
    s.add_argument("state", choices=STATES)
    s.add_argument("--note", default="")
    s.add_argument("--next", default="", dest="next_action")
    sub.add_parser("list")
    sh = sub.add_parser("show")
    sh.add_argument("key")
    args = ap.parse_args()

    tracker = load()
    if args.cmd == "set":
        row = set_state(tracker, args.key, args.state, args.note, args.next_action, find_match(args.key))
        save(tracker)
        print(f"{args.key}: {row['state']}  ({row['company']} | {row['title']})")
    elif args.cmd == "show":
        print(json.dumps(tracker.get(args.key, {}), indent=1, ensure_ascii=False))
    else:
        for key, row in sorted(tracker.items(), key=lambda kv: kv[1].get("updated", ""), reverse=True):
            print(f"{row.get('state', '?'):<10} {row.get('updated', '')}  {row.get('company', '')} | {row.get('title', '')}"
                  + (f"  next: {row['next']}" if row.get("next") else ""))
            print(f"           {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Move data between the repo and the dashboard Worker.

    .venv/bin/python -m scout.sync push     # matches, page state, config text, tracker  -> Worker KV
    .venv/bin/python -m scout.sync pull     # tracker, prep queue, passed keys  <- Worker KV, into data/
    .venv/bin/python -m scout.sync push --tracker-only   # just data/tracker.json -> Worker KV (after /prep or /status)

--tracker-only exists because the Mac's data/matches.json is an old copy: a full push from the Mac would
replace the dashboard's matches with it. The tracker merges per posting, newer "updated" wins.

Needs two settings, from the environment or from me/dashboard.env (gitignored, KEY=value lines):
    SCOUT_URL            https://scout-dashboard.<account>.workers.dev
    SCOUT_INGEST_SECRET  the same value as the Worker's INGEST_SECRET

In GitHub Actions both come from repository secrets. Without them, both commands print a note and exit 0,
so a missing dashboard never breaks the cron.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ENV_FILE = ROOT / "me" / "dashboard.env"


def settings() -> tuple[str, str] | None:
    env = dict(os.environ)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    url, secret = env.get("SCOUT_URL", "").rstrip("/"), env.get("SCOUT_INGEST_SECRET", "")
    return (url, secret) if url and secret else None


def _load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def _call(url: str, secret: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    # Cloudflare answers 403 to Python's default "Python-urllib" User-Agent before the Worker ever sees
    # the request, so the sync identifies itself by name.
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"x-scout-secret": secret, "Content-Type": "application/json",
                                              "User-Agent": "scout-sync/0.1 (GitHub Actions cron)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def build_push_payload(data_dir: Path = DATA, config_dir: Path = ROOT / "config") -> dict:
    """Everything the dashboard shows, from the files the cron just wrote.

    Not the tracker: the cron never changes it, and sending back the copy it pulled minutes earlier would undo
    a phone edit made in between (both stamp the same date). /prep and /status use push --tracker-only."""
    matches = _load(data_dir / "matches.json", {"matches": [], "counts": {}, "generated_at": ""})
    seen = _load(data_dir / "seen.json", {})
    for m in matches["matches"]:
        m["first_seen"] = (seen.get(m["key"]) or {}).get("at", "")
    config_text = {}
    for name, key in (("targets.yaml", "targets"), ("scoring.yaml", "scoring"), ("watch-pages.yaml", "watch_pages")):
        p = config_dir / name
        config_text[key] = p.read_text(encoding="utf-8") if p.exists() else ""
    return {
        "generated_at": matches.get("generated_at", ""),
        "counts": matches.get("counts", {}),
        "total_matches": matches.get("total_matches", len(matches["matches"])),  # matches.json holds only the top 300
        "open_total": matches.get("open_total", matches.get("total_matches", len(matches["matches"]))),
        "matches": matches["matches"],
        "pages": _load(data_dir / "pages.json", {}),
        "config_text": config_text,
    }


def apply_pull(state: dict, data_dir: Path = DATA) -> dict:
    """Write what the phone changed into data/. Returns a summary. The Worker already merged the tracker."""
    data_dir.mkdir(parents=True, exist_ok=True)
    tracker = state.get("tracker", {})
    (data_dir / "tracker.json").write_text(json.dumps(tracker, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    queue = state.get("queue", [])
    (data_dir / "queue.json").write_text(json.dumps(queue, indent=1), encoding="utf-8")
    passed = state.get("passed", {})
    (data_dir / "passed.json").write_text(json.dumps(passed, indent=1, sort_keys=True), encoding="utf-8")
    return {"tracker": len(tracker), "queue": len(queue), "passed": len(passed)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["push", "pull"])
    ap.add_argument("--tracker-only", action="store_true", help="push: send only data/tracker.json")
    args = ap.parse_args()
    cfg = settings()
    if not cfg:
        print("sync skipped: SCOUT_URL and SCOUT_INGEST_SECRET are not set")
        return 0
    url, secret = cfg
    try:
        if args.command == "push" and args.tracker_only:
            result = _call(f"{url}/api/ingest-tracker", secret, "POST", {"tracker": _load(DATA / "tracker.json", {})})
            print(f"pushed tracker ({result.get('tracker', 0)} rows on the dashboard)")
        elif args.command == "push":
            result = _call(f"{url}/api/ingest", secret, "POST", build_push_payload())
            print(f"pushed {result.get('matches', 0)} matches to the dashboard")
        else:
            summary = apply_pull(_call(f"{url}/api/export", secret))
            print(f"pulled tracker ({summary['tracker']}), queue ({summary['queue']}), passed ({summary['passed']})")
    except Exception as exc:
        print(f"sync {args.command} failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The entry point the cron calls. One command, three modes.

    .venv/bin/python -m scout.run --mode watch            # every 3 hours: score, instant pushes, page watchers
    .venv/bin/python -m scout.run --mode digest           # 7:00 PM ET: the daily digest (exits quietly at other hours)
    .venv/bin/python -m scout.run --mode test             # one test push to the phone
    .venv/bin/python -m scout.run --mode watch --dry-run  # print what would be sent, send nothing, save nothing

NTFY_TOPIC must be set in the environment (a GitHub Actions secret in the cron, exported by hand locally).
Without it, every mode runs as a dry run.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from scout import alerts, listings, matching, notify, pages, scoring, watch

ROOT = Path(__file__).resolve().parent.parent
DIGEST_HOUR_ET = 19  # 7:00 PM


class Sender:
    """Wraps Ntfy so a dry run prints instead of posting."""

    def __init__(self, topic: str | None, dry_run: bool):
        self.dry_run = dry_run or not topic
        self.ntfy = notify.Ntfy(topic) if topic else None
        self.sent = 0
        self.failed = 0

    def send(self, push: dict) -> bool:
        line = f"[{'DRY' if self.dry_run else 'PUSH'}] {push['title']}\n    " + push["message"].replace("\n", "\n    ")
        print(line)
        if self.dry_run:
            return True
        ok = self.ntfy.send(push["title"], push["message"], push.get("click"), push.get("priority", 3), push.get("tags"))
        self.sent += ok
        self.failed += (not ok)
        return ok


def score_everything(sender: Sender, now: float, allow_network: bool = True):
    targets = matching.load_targets()
    weights = scoring.load_weights()
    raw, errors = listings.fetch_all()
    for err in errors:
        print(f"SOURCE ERROR: {err}", file=sys.stderr)
        sender.send(notify.failure_push("source fetch", err))
    if not raw:
        return [], weights
    matches, counts = watch.run(raw, targets, weights, check_pages=40, allow_network=allow_network, now=now)
    if not sender.dry_run:
        watch.write_matches(matches, counts)
    print(f"scored {len(matches)} matches " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return matches, weights


def mode_watch(sender: Sender, now: float, seed: bool = False) -> None:
    matches, weights = score_everything(sender, now)
    seen = alerts.load_seen()
    if seed:
        # First run only: everything that exists today counts as already seen, so the phone
        # gets alerts for what appears from now on, not a flood of a thousand old postings.
        fresh = [m for m in matches if m["key"] not in seen]
        alerts.mark_seen(seen, fresh, "seeded", now)
        print(f"seeded {len(fresh)} existing matches as seen; no pushes")
    else:
        instant = alerts.select_instant(matches, seen, weights)
        print(f"{len(instant)} instant alert(s)")
        sent = [m for m in instant if sender.send(notify.match_push(m, now))]
        alerts.mark_seen(seen, sent, "instant", now)

    page_list = pages.load_pages()
    state = pages.load_state()
    events = pages.check_pages(page_list, state, now=now)
    for ev in events:
        print(f"page {ev['kind']}: {ev['name']}: {ev['summary'].splitlines()[0] if ev['summary'] else ''}")
        if ev["kind"] in ("changed", "unreadable", "thin"):
            sender.send(notify.page_push(ev))
    if not sender.dry_run:
        alerts.save_seen(seen)
        pages.save_state(state)


def mode_digest(sender: Sender, now: float, force: bool = False) -> None:
    hour = notify.et_hour(now)
    if hour != DIGEST_HOUR_ET and not force:
        print(f"digest skipped: it is {hour}:00 in New York, the digest goes out at 7:00 PM")
        return
    matches, weights = score_everything(sender, now, allow_network=False)
    seen = alerts.load_seen()
    chosen = alerts.select_digest(matches, seen, weights)
    sender.send(notify.digest_push(chosen, now))
    alerts.mark_seen(seen, chosen, "digest", now)
    if not sender.dry_run:
        alerts.save_seen(seen)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Scout once.")
    ap.add_argument("--mode", choices=["watch", "digest", "test"], required=True)
    ap.add_argument("--dry-run", action="store_true", help="print pushes, send nothing, save nothing")
    ap.add_argument("--force", action="store_true", help="digest: send even outside 7:00 PM ET")
    ap.add_argument("--seed", action="store_true", help="watch: mark everything current as seen, push nothing (first run)")
    args = ap.parse_args()

    topic = notify.topic_from_env()
    sender = Sender(topic, args.dry_run)
    if sender.dry_run:
        print("dry run" + ("" if topic else " (NTFY_TOPIC not set)"))
    now = time.time()

    if args.mode == "test":
        sender.send(notify.test_push())
    elif args.mode == "watch":
        mode_watch(sender, now, seed=args.seed)
    else:
        mode_digest(sender, now, args.force)

    if sender.failed:
        print(f"{sender.failed} push(es) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

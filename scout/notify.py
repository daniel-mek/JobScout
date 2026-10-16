"""Push notifications through ntfy (free, no account, iPhone app).

A topic is just a name; anyone who knows it can read the topic, so it is a long random string kept in
the NTFY_TOPIC secret. Messages carry company, role, location, score, and link. Nothing personal, ever.

The shape of the POST was checked against ntfy's documented JSON publish format and against
JDKrasnick/Ntern's NtfyPublisher (MIT), which does the same thing in TypeScript.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_SERVER = "https://ntfy.sh"
ET = ZoneInfo("America/New_York")


def topic_from_env() -> str | None:
    return os.environ.get("NTFY_TOPIC") or None


class Ntfy:
    """Sends one message. Pass a fake `sender` in tests so nothing leaves the machine."""

    def __init__(self, topic: str, server: str = DEFAULT_SERVER, sender=None):
        self.topic = topic
        self.server = server.rstrip("/")
        self.sender = sender or self._post

    def _post(self, payload: dict) -> bool:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.server, data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200 <= response.status < 300

    def send(self, title: str, message: str, click: str | None = None, priority: int = 3,
             tags: list[str] | None = None) -> bool:
        payload = {"topic": self.topic, "title": title[:200], "message": message[:3800], "priority": priority}
        if click:
            payload["click"] = click
        if tags:
            payload["tags"] = tags
        try:
            return bool(self.sender(payload))
        except Exception:
            return False


# ---------------------------------------------------------------- message shapes

def _location(m: dict) -> str:
    locs = m.get("locations", [])
    if not locs:
        return "location not listed"
    text = ", ".join(locs[:2])
    return text + (f" (+{len(locs) - 2} more)" if len(locs) > 2 else "")


def _age(m: dict, now: float) -> str:
    days = int((now - m["date_posted"]) // 86400) if m.get("date_posted") else None
    return "posted today" if days == 0 else f"posted {days}d ago" if days is not None else "posted ?"


def match_push(m: dict, now: float) -> dict:
    """One instant alert for one posting."""
    why = []
    if m.get("early_career") == "strong":
        why.append("freshman/sophomore program")
    if m.get("role") == "ambassador":
        why.append("ambassador program")
    if m.get("tier", 3) <= 2:
        why.append(f"Tier {m['tier']}")
    elig = m.get("eligibility", "unknown")
    lines = [
        _location(m),
        f"Score {m['score']} ({', '.join(why) or 'match'}), {_age(m, now)}",
        f"Eligibility: {elig}, {m['eligibility_note']}" if elig != "unknown" and m.get("eligibility_note")
        else "Eligibility: unknown, check the graduation year before you apply",
    ]
    if m.get("citizens_only"):
        lines.append("US citizens only")
    # Only a page that names his graduation year (or says freshman) gets the loud push.
    # An unread page still alerts, quietly, because "unknown" is never hidden.
    if elig != "ok":
        priority = 3
    else:
        priority = 5 if m.get("early_career") == "strong" else 4
    return {
        "title": f"{m['company']}: {m['title']}"[:120],
        "message": "\n".join(lines),
        "click": m.get("url"),
        "priority": priority,
        "tags": ["star2"] if m.get("early_career") == "strong" else ["briefcase"],
    }


def digest_push(matches: list[dict], now: float) -> dict:
    """The 7:00 PM digest: top matches that were not alerted instantly."""
    if not matches:
        return {"title": "Scout digest: nothing new today", "message": "No new matches passed the filters since the last digest.",
                "priority": 2, "tags": ["zzz"]}
    lines = []
    for m in matches:
        lines.append(f"{m['score']} {m['company']}: {m['title']} ({_location(m)}, {_age(m, now)})\n{m['url']}")
    return {"title": f"Scout digest: {len(matches)} new matches", "message": "\n\n".join(lines),
            "priority": 3, "tags": ["newspaper"]}


def page_push(event: dict) -> dict:
    kind = event["kind"]
    if kind == "changed":
        return {"title": f"Page changed: {event['name']}", "message": event["summary"], "click": event["url"],
                "priority": 4, "tags": ["eyes"]}
    if kind == "unreadable":
        return {"title": f"Scout: can't read {event['name']}", "message": event["summary"], "click": event["url"],
                "priority": 2, "tags": ["warning"]}
    return {"title": f"Scout: {event['name']} needs a better URL", "message": event["summary"], "click": event["url"],
            "priority": 2, "tags": ["warning"]}


def failure_push(what: str, detail: str) -> dict:
    return {"title": f"Scout: {what} failed", "message": detail[:500], "priority": 3, "tags": ["warning"]}


def test_push() -> dict:
    return {"title": "Scout is connected", "message": "This is the one test push. Alerts from here on are real matches.",
            "priority": 3, "tags": ["white_check_mark"]}


def et_hour(now: float | None = None) -> int:
    """Hour of the day in New York, 0 to 23. GitHub cron runs in UTC and cannot follow daylight saving."""
    dt = datetime.fromtimestamp(now, ET) if now is not None else datetime.now(ET)
    return dt.hour

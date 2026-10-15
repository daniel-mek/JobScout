"""Watch program pages for changes.

Big tech freshman programs (Microsoft Explore, Google STEP, NVIDIA Ignite, Meta University) often open
without ever showing up in the internship lists, so Scout watches the official pages themselves.
Each run fetches every page in config/watch-pages.yaml, strips it to plain text, and compares a hash
of that text with the last run. When it changes, Scout alerts with the first few new sentences.

State lives in data/pages.json (one record per URL) and data/pages/<slug>.txt (the last text seen,
so the next change can be described, not just detected). Both are committed by the cron.

Pages are untrusted text: they are only ever hashed, diffed, and quoted, never followed or executed.
"""

from __future__ import annotations

import difflib
import hashlib
import html
import json
import re
import time
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "watch-pages.yaml"
STATE_PATH = ROOT / "data" / "pages.json"
TEXT_DIR = ROOT / "data" / "pages"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
THIN_PAGE_CHARS = 400          # less text than this means the page is a JavaScript app we cannot read
FAILURES_BEFORE_ALERT = 2      # one bad fetch is noise; two in a row is worth a message

_TAGS = re.compile(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>|<!--.*?-->|<[^>]+>", re.S | re.I)
# Things that change on every load without meaning anything: hex hashes, long tokens, big numbers,
# and the cloud region a page was served from (Amazon's page says us-east-1 or us-west-2 depending on
# which server answered, which is what set off the very first alert).
_NOISE = [
    re.compile(r"\b[0-9a-f]{16,}\b", re.I),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),
    re.compile(r"\b\d{6,}\b"),
    re.compile(r"\b[a-z]{2}-(?:[a-z]+-)+\d\b", re.I),
]
MEANINGFUL_LINE_CHARS = 12   # an added line shorter than this is a token, not a sentence


def load_pages(path: Path = CONFIG_PATH) -> list[dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return [p for p in data.get("pages", []) if p.get("url")]


def slug(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")[:80]


_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def drop_job_carousels(lines: list[str]) -> list[str]:
    """Remove rotating "latest jobs" cards: a title, then a date line, then a few lines, then "See details".

    Microsoft's program pages show a carousel of whatever jobs were posted most recently, so the page
    "changes" every day without the program changing at all. A card is any run that starts one line
    before a bare YYYY-MM-DD line and ends at the next "See details" within eight lines.
    """
    out: list[str] = []
    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and _ISO_DATE.fullmatch(lines[i + 1]):
            end = next((j for j in range(i + 2, min(i + 9, len(lines))) if lines[j].lower() == "see details"), None)
            if end is not None:
                i = end + 1
                continue
        out.append(lines[i])
        i += 1
    return out


def html_to_text(raw: str) -> str:
    """Strip HTML to readable text, one sentence or line per row, with noise tokens and job carousels removed."""
    text = html.unescape(_TAGS.sub("\n", raw))
    for pattern in _NOISE:
        text = pattern.sub("", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(drop_job_carousels([line for line in lines if len(line) >= 3]))


def fetch_text(url: str, timeout: int = 25) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(3_000_000).decode("utf-8", errors="replace")
    except Exception:
        return None
    return html_to_text(raw)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def added_lines(old: str, new: str) -> list[str]:
    """Lines present in the new text and absent from the old, ignoring short tokens."""
    added = [line[2:] for line in difflib.ndiff(old.splitlines(), new.splitlines()) if line.startswith("+ ")]
    return [a for a in added if len(a) >= MEANINGFUL_LINE_CHARS]


def summarize_change(old: str, new: str, limit: int = 4) -> str:
    """The first few lines that are new on the page, so the alert says what changed."""
    added = added_lines(old, new)[:limit]
    return "\n".join(f"+ {a[:140]}" for a in added) if added else "(text changed, nothing new added; something was removed or reordered)"


def load_state(path: Path = STATE_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")


def check_pages(pages: list[dict], state: dict, fetch=fetch_text, text_dir: Path = TEXT_DIR,
                now: float | None = None) -> list[dict]:
    """Fetch every page, update state in place, and return the events worth a push.

    Event kinds: "changed" (alert: new lines appeared), "shuffled" (no alert: lines removed or reordered),
    "unreadable" (alert, after two failures in a row), "thin" (alert once: the page gives a server
    no text, so a better URL is needed), "baseline" (first time seen, no alert).
    """
    now = now if now is not None else time.time()
    text_dir.mkdir(parents=True, exist_ok=True)
    events: list[dict] = []

    for page in pages:
        url, name = page["url"], page.get("name", page["url"])
        record = state.setdefault(url, {"name": name, "hash": None, "text_len": 0, "failures": 0,
                                        "checked_at": 0, "changed_at": 0, "thin_alerted": False})
        record["name"] = name
        record["checked_at"] = int(now)
        text = fetch(url)

        if text is None:
            record["failures"] += 1
            if record["failures"] == FAILURES_BEFORE_ALERT:
                events.append({"kind": "unreadable", "name": name, "url": url,
                               "summary": f"could not be read {FAILURES_BEFORE_ALERT} runs in a row"})
            continue
        record["failures"] = 0

        if len(text) < THIN_PAGE_CHARS and not record["thin_alerted"]:
            record["thin_alerted"] = True
            events.append({"kind": "thin", "name": name, "url": url,
                           "summary": f"only {len(text)} characters of text reach a server; this page needs a different URL"})

        new_hash = text_hash(text)
        text_file = text_dir / f"{slug(url)}.txt"
        if record["hash"] is None:
            events.append({"kind": "baseline", "name": name, "url": url, "summary": "first time seen, baseline saved"})
        elif new_hash != record["hash"]:
            old = text_file.read_text(encoding="utf-8") if text_file.exists() else ""
            # Only new sentences are worth a push. A removed or reordered line (or a leftover token
            # the noise filter missed) is recorded in the state but never alerted.
            kind = "changed" if added_lines(old, text) else "shuffled"
            summary = summarize_change(old, text)
            events.append({"kind": kind, "name": name, "url": url, "summary": summary})
            if kind == "changed":
                # Only real changes (new sentences) count as "changed" on the dashboard,
                # and the new lines are kept so the card can show what is different.
                record["changed_at"] = int(now)
                record["last_change"] = summary
        record["hash"] = new_hash
        record["text_len"] = len(text)
        text_file.write_text(text, encoding="utf-8")
    return events

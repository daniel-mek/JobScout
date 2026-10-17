"""Read public Greenhouse, Lever, and Ashby boards for early-career roles.

Only explicit full-time junior, entry-level, and new-graduate titles are collected.
The downstream matcher limits results to the configured IT/CS role families.
Board text is untrusted data and is never executed.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone

from scout import career

USER_AGENT = "jobscout-early-career-watcher/0.1 (personal project; reads public job boards only)"
def _get(url: str, timeout: int = 30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _split_places(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\s*[;•|]\s*", text or "") if p.strip()]


def _row(company: str, board: str, job_id: str, title: str, url: str, places: list[str], posted: int,
         now: datetime | None) -> dict:
    return {"id": f"{board}:{job_id}", "source": "boards", "company": company, "title": title.strip(), "url": url,
            "locations": places, "career_level": career.level(title), "terms": [], "degrees": [], "sponsorship": "Other",
            "category": None, "date_posted": posted, "date_updated": posted, "active": True}


def _iso_seconds(text: str) -> int:
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except (AttributeError, ValueError):
        return 0


def greenhouse(board: str, company: str, now: datetime | None = None, fetch=_get) -> list[dict]:
    rows = []
    for job in fetch(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs").get("jobs", []):
        if not career.board_candidate(job.get("title", "")):
            continue
        absolute = job.get("absolute_url", "")
        # Lists link greenhouse-hosted jobs without the ?gh_jid echo, and company-hosted ones with it.
        url = (f"https://boards.greenhouse.io/{board}/jobs/{job['id']}" if "greenhouse.io" in absolute else absolute)
        posted = _iso_seconds(job.get("first_published") or job.get("updated_at") or "")
        rows.append(_row(company, board, str(job["id"]), job["title"], url,
                         _split_places((job.get("location") or {}).get("name", "")), posted, now))
    return rows


def ashby(org: str, company: str, now: datetime | None = None, fetch=_get) -> list[dict]:
    rows = []
    for job in fetch(f"https://api.ashbyhq.com/posting-api/job-board/{org}").get("jobs", []):
        if not career.board_candidate(job.get("title", "")) or job.get("isListed") is False:
            continue
        places = [job.get("location", "")] + [s.get("location", "") for s in job.get("secondaryLocations") or []]
        rows.append(_row(company, org, job["id"], job["title"], f"https://jobs.ashbyhq.com/{org}/{job['id']}",
                         [p for p in places if p], _iso_seconds(job.get("publishedAt", "")), now))
    return rows


def lever(org: str, company: str, now: datetime | None = None, fetch=_get) -> list[dict]:
    rows = []
    for job in fetch(f"https://api.lever.co/v0/postings/{org}?mode=json"):
        if not career.board_candidate(job.get("text", "")):
            continue
        categories = job.get("categories") or {}
        places = categories.get("allLocations") or [categories.get("location", "")]
        rows.append(_row(company, org, job["id"], job["text"], job.get("hostedUrl", ""),
                         [p for p in places if p], int(job.get("createdAt") or 0) // 1000, now))
    return rows


READERS = {"greenhouse": greenhouse, "ashby": ashby, "lever": lever}


def fetch_boards(config: dict, now: datetime | None = None) -> tuple[list[dict], list[str]]:
    """All boards in targets.yaml. One board failing never hides the others; its error is returned."""
    rows: list[dict] = []
    errors: list[str] = []
    for kind, boards in (config or {}).items():
        reader = READERS.get(kind)
        if reader is None:
            errors.append(f"boards: unknown board type {kind!r}")
            continue
        for board, company in (boards or {}).items():
            try:
                rows.extend(reader(board, company, now))
            except Exception as exc:  # a 404 or a timeout on one board: report it, keep going
                errors.append(f"boards: {kind} {board}: {exc}")
    return rows, errors


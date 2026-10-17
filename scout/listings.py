"""Fetch public full-time new-graduate and company ATS listings.

Legacy normalizers remain available for reading previously saved source data.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import yaml

from scout import boards, career

SOURCES = {
    "simplify_newgrad": "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
}

USER_AGENT = "jobscout-early-career-watcher/0.1 (personal project; reads public JSON only)"


class SourceError(Exception):
    """A source could not be fetched or did not look like the list we expect. The caller alerts loudly."""


def fetch_json(url: str, timeout: int = 60) -> list:
    """Download one source file. Raises SourceError on any failure so the run can fail loudly."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except Exception as exc:  # network error, timeout, bad JSON: all the same to the caller
        raise SourceError(f"fetch failed for {url}: {exc}") from exc
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise SourceError(f"unexpected shape from {url}: expected a non-empty list of objects")
    return data


def load_json(path: Path) -> list:
    """Read a saved copy of a source file (fixtures in tests, or --offline runs)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_simplify(row: dict) -> dict:
    return {
        "id": str(row.get("id", "")),
        "source": "simplify",
        "company": (row.get("company_name") or "").strip(),
        "title": (row.get("title") or "").strip(),
        "url": (row.get("url") or "").strip(),
        "locations": [str(x).strip() for x in (row.get("locations") or []) if x],
        "terms": [str(x).strip() for x in (row.get("terms") or []) if x],
        "degrees": [str(x).strip() for x in (row.get("degrees") or []) if x],
        "sponsorship": (row.get("sponsorship") or "Other").strip(),
        "category": row.get("category") or None,
        "date_posted": int(row.get("date_posted") or 0),
        "date_updated": int(row.get("date_updated") or row.get("date_posted") or 0),
        "active": bool(row.get("active")) and bool(row.get("is_visible", True)),
    }


def normalize_vanshb03(row: dict) -> dict:
    # This list has a "season" ("Summer", "Fall", "Winter", "Spring", "Spring/Summer") but no year.
    # The repo itself is the 2027 cycle, so the year is filled in here. "null" means the row did not say.
    season = (row.get("season") or "").strip()
    terms = [f"{season} 2027"] if season and season.lower() != "null" else []
    return {
        "id": str(row.get("id", "")),
        "source": "vanshb03",
        "company": (row.get("company_name") or "").strip(),
        "title": (row.get("title") or "").strip(),
        "url": (row.get("url") or "").strip(),
        "locations": [str(x).strip() for x in (row.get("locations") or []) if x],
        "terms": terms,
        "degrees": [],  # the list does not record degrees
        "sponsorship": (row.get("sponsorship") or "Other").strip(),
        "category": None,
        "date_posted": int(row.get("date_posted") or 0),
        "date_updated": int(row.get("date_updated") or row.get("date_posted") or 0),
        "active": bool(row.get("active")) and bool(row.get("is_visible", True)),
    }


def normalize_newgrad(row: dict) -> dict:
    item = normalize_simplify(row)
    item["source"] = "simplify_newgrad"
    item["career_level"] = career.level(item["title"], curated_newgrad=True)
    return item


NORMALIZERS = {"simplify_newgrad": normalize_newgrad, "simplify": normalize_simplify, "vanshb03": normalize_vanshb03, "boards": lambda row: row}
TARGETS_PATH = Path(__file__).resolve().parent.parent / "config" / "targets.yaml"


def normalize_all(raw_by_source: dict[str, list]) -> list[dict]:
    """{"simplify": [...rows...], "vanshb03": [...rows...]} -> one flat list of normalized dicts."""
    out: list[dict] = []
    for source, rows in raw_by_source.items():
        normalize = NORMALIZERS[source]
        for row in rows:
            item = normalize(row)
            if item["company"] and item["title"]:
                out.append(item)
    return out


def fetch_all(sources: dict[str, str] | None = None, with_boards: bool = True) -> tuple[dict[str, list], list[str]]:
    """Fetch every source. Returns (raw rows by source, list of error messages).

    One broken source must not hide the other, so errors are collected, not raised.
    The caller decides whether to alert on them.
    """
    sources = SOURCES if sources is None else sources
    raw: dict[str, list] = {}
    errors: list[str] = []
    for name, url in sources.items():
        try:
            raw[name] = fetch_json(url)
        except SourceError as exc:
            errors.append(f"{name}: {exc}")
    if with_boards:
        config = (yaml.safe_load(TARGETS_PATH.read_text(encoding="utf-8")) or {}).get("boards") or {}
        rows, board_errors = boards.fetch_boards(config)
        raw["boards"] = rows
        errors.extend(board_errors)
    return raw, errors


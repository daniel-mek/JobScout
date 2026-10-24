"""Literal qualification comparisons; no invented experience or equivalence."""

import re
from datetime import UTC, datetime

CERTIFICATES = ("CCNA", "CISSP", "CompTIA Security+", "Security+", "AWS Certified Cloud Practitioner")
SUBJECTS = ("computer science", "information technology", "information systems", "engineering", "mathematics")


def professional_months(profile, at=None):
    intervals = []
    unknown = False
    now = at or datetime.now(UTC)
    for entry in profile.get("experience", []):
        # Projects and education are never inputs. Ambiguous year-only dates stay unknown.
        match = re.fullmatch(
            r"\s*(\d{4})-(\d{2})\s*(?:to|[-–—])\s*(?:(\d{4})-(\d{2})|(present|current))\s*",
            entry.get("dates", ""),
            re.I,
        )
        if not match:
            unknown = True
            continue
        year, month = int(match[1]), int(match[2])
        end_year, end_month = (int(match[3]), int(match[4])) if match[3] else (now.year, now.month)
        if not 1 <= month <= 12 or not 1 <= end_month <= 12:
            unknown = True
            continue
        start, end = year * 12 + month, end_year * 12 + end_month
        if end < start or end > now.year * 12 + now.month:
            unknown = True
            continue
        # Internships remain valid history, but are not silently counted as professional tenure.
        if re.search(r"\bintern(ship)?\b", entry.get("title", ""), re.I):
            unknown = True
            continue
        intervals.append((start, end))
    months, last = 0, -1
    for start, end in sorted(intervals):
        months += max(0, end - max(start, last))
        last = max(last, end)
    return months if intervals and not unknown else None


def degree_level(text):
    if re.search(r"\b(ph\.?d|doctorate|doctoral)\b", text, re.I):
        return 3
    if re.search(r"\b(master|msc|m\.?s\.?)\b", text, re.I):
        return 2
    if re.search(r"\b(bachelor|bsc|b\.?s\.?|b\.?a\.?)\b", text, re.I):
        return 1
    return None


def education_fit(requirements, profile):
    required = [r for r in requirements if r["kind"] == "education" and r["obligation"] == "required"]
    if not required:
        return 50, "No explicit required education extracted; unknown is neutral."
    degrees = [x.get("degree", "") for x in profile.get("education", [])]
    results = []
    for requirement in required:
        text = requirement["evidence"]
        level = degree_level(text)
        subjects = [s for s in SUBJECTS if s in text.casefold()]
        if level is None or re.search(r"equivalent|or experience", text, re.I):
            results.append(50)
        elif any(
            (degree_level(d) or 0) >= level and (not subjects or any(s in d.casefold() for s in subjects))
            for d in degrees
        ):
            results.append(100)
        else:
            results.append(0)
    return min(results), "Literal confirmed degree level/subject comparison; equivalence remains unknown."


def certification_fit(requirements, profile):
    texts = [
        r["evidence"] for r in requirements if r["kind"] == "certification" and r["obligation"] == "required"
    ]
    names = {name for text in texts for name in CERTIFICATES if re.search(re.escape(name), text, re.I)}
    candidate = "\n".join(x.get("name", "") for x in profile.get("certifications", []))
    missing = [name for name in sorted(names) if not re.search(re.escape(name), candidate, re.I)]
    return (round(100 * (len(names) - len(missing)) / len(names)) if names else 50), missing


def country_code(value):
    known = {
        "usa": "US",
        "united states": "US",
        "united states of america": "US",
        "can": "CA",
        "canada": "CA",
        "united kingdom": "GB",
        "uk": "GB",
    }.get(str(value).casefold())
    text = str(value).upper()
    return known or (text if len(text) == 2 and text.isascii() and text.isalpha() else None)

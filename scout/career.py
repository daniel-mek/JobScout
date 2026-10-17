"""Conservative title signals for early-career jobs; no invented experience requirements."""

import re

INTERN = re.compile(r"\b(interns?|internship|co-?op|fellows?|fellowship)\b", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head|vp|chief)\b|\b(?:engineer|developer|analyst)\s+(?:[2-9]|ii|iii|iv)\b", re.I)
ENTRY = re.compile(r"\b(new[- ]grad(?:uate)?s?|recent[- ]graduates?|university[- ]graduates?|entry[- ]level|early[- ]careers?|junior|jr\.?|associate|graduate)\b|\b(?:engineer|developer|analyst|technician)\s+(?:1|i)\b|\btier[- ]?1\b", re.I)


def level(title: str, curated_newgrad: bool = False) -> str:
    # "Member of Technical Staff" is also used for graduate roles; Staff Engineer is senior.
    senior_title = re.sub(r"\b(?:member of (?:the )?)?technical staff\b", "", title or "", flags=re.I)
    if SENIOR.search(senior_title):
        return "experienced"
    if INTERN.search(title or ""):
        return "internship"
    if ENTRY.search(title or "") or curated_newgrad:
        return "entry_level"
    return "unknown"


def board_candidate(title: str) -> bool:
    return level(title) in ("internship", "entry_level")

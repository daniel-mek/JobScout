import re
from datetime import UTC, datetime

VERSION = "rules-1"
MATCH_WEIGHTS = dict(skills=35, experience=20, role=15, education=10, location=10, preferences=5, other=5)
PRIORITY_WEIGHTS = dict(match=55, freshness=15, early_career=10, location=5, salary=5, company=5, source=5)
ALIASES = {"js": "javascript", "postgres": "postgresql", "amazon web services": "aws"}
VOCABULARY = [
    "Python",
    "JavaScript",
    "TypeScript",
    "Java",
    "SQL",
    "PostgreSQL",
    "AWS",
    "Docker",
    "Linux",
    "Git",
    "React",
    "Azure",
    "Kubernetes",
    "PowerShell",
    "Bash",
    "TCP/IP",
    "Cisco",
    "Excel",
    "C++",
    "C#",
    ".NET",
    "Terraform",
]


def alias(value):
    value = value.strip().casefold()
    return ALIASES.get(value, value)


def extract(data):
    requirements, skills = [], []
    minimum = data.get("experience_min")
    for line in re.split(
        r"[\n.!?](?!\w)|\n",
        "\n".join(
            filter(None, [data.get("description"), data.get("requirements"), data.get("responsibilities")])
        ),
    ):
        line = line.strip()[:2000]
        if not line:
            continue
        preferred = bool(re.search(r"\b(preferred|nice to have|bonus|plus|ideally)\b", line, re.I))
        obligation = (
            "preferred"
            if preferred
            else "required"
            if re.search(
                r"\b(required|must|minimum|requirements|qualifications|no sponsorship|cannot sponsor|unable to sponsor)\b",
                line,
                re.I,
            )
            else "uncertain"
        )
        for name in VOCABULARY + list(ALIASES):
            if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", line, re.I):
                skills.append(
                    dict(
                        name=alias(name),
                        obligation=obligation,
                        evidence=line,
                        confidence=0.95 if obligation != "uncertain" else 0.5,
                    )
                )
        years = re.search(
            r"(?<!\d)(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\s*\+?\s*years?\s+(?:of\s+)?(?:relevant\s+|professional\s+)?experience",
            line,
            re.I,
        )
        if years:
            value = int(years[1])
            requirements.append(
                dict(
                    kind="experience",
                    value=value,
                    obligation=obligation,
                    evidence=line,
                    confidence=0.95 if obligation != "uncertain" else 0.5,
                )
            )
            if obligation == "required":
                minimum = max(minimum or 0, value)
        for kind, pattern in {
            "education": r"\b(bachelor|master|ph\.?d|degree)\b",
            "certification": r"\b(certification|certified|CISSP|CCNA|Security\+)\b",
            "clearance": r"\b(active|current|required|must).{0,40}\b(security clearance|secret clearance|top secret)\b",
            "authorization": r"\b(no sponsorship|cannot sponsor|unable to sponsor|authorized to work|citizenship required)\b",
            "location": r"\b(relocat|on.site|hybrid|remote|must reside)\w*",
        }.items():
            if re.search(pattern, line, re.I):
                requirements.append(
                    dict(
                        kind=kind,
                        value=line,
                        obligation=obligation,
                        evidence=line,
                        confidence=0.8 if obligation != "uncertain" else 0.5,
                    )
                )
    title = data.get("title", "").lower()
    level = "UNKNOWN"
    if minimum is not None:
        level = (
            "SENIOR"
            if minimum >= 5
            else "MID_LEVEL"
            if minimum >= 4
            else "REASONABLE_REACH"
            if minimum >= 3
            else "EARLY_CAREER"
            if minimum >= 1
            else "TRUE_ENTRY_LEVEL"
        )
    elif re.search(r"\b(senior|lead|principal|staff|architect|manager)\b", title):
        level = "SENIOR"
    elif re.search(r"\b(new grad|recent graduate|rotational)\b", title):
        level = "NEW_GRAD"
    elif re.search(r"\b(junior|entry.level|associate|engineer i)\b", title):
        level = "TRUE_ENTRY_LEVEL"
    unique = {(x["name"], x["obligation"], x["evidence"]): x for x in skills}
    return dict(
        requirements=requirements, skills=list(unique.values()), experience_min=minimum, early_career=level
    )


def weighted(parts, weights):
    if set(parts) != set(weights) or any(v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Invalid scoring weights")
    return round(sum(parts[k] * v for k, v in weights.items()) / sum(weights.values()))


def calculate(data, profile, preferences, hard, *, at=None, match_weights=None, priority_weights=None):
    extracted = extract(data)
    warnings, failures, unknown = [], [], []
    if not data.get("active", True):
        failures.append("Listing is archived.")
    minimum = extracted["experience_min"]
    if hard.get("max_requested_experience") is not None:
        if minimum is None:
            unknown.append("Required experience is unknown.")
        elif minimum > hard["max_requested_experience"]:
            failures.append("Required experience exceeds your explicit cap.")
    if hard.get("allow_contract") is False:
        if data.get("employment_type") is None:
            unknown.append("Employment type is unknown.")
        elif data["employment_type"] == "CONTRACT":
            failures.append("Contract work conflicts with your hard requirements.")
    if hard.get("countries"):
        if not data.get("country"):
            unknown.append("Job country is unknown.")
        elif data["country"].casefold() not in [x.casefold() for x in hard["countries"]]:
            failures.append("Country conflicts with your geographic requirements.")
    for req in extracted["requirements"]:
        if req["obligation"] != "required":
            continue
        if req["kind"] == "clearance" and hard.get("allow_clearance") is False:
            failures.append("Posting requires clearance; your settings exclude it.")
        if req["kind"] == "authorization":
            if hard.get("needs_sponsorship") is True and re.search(
                r"no sponsorship|cannot sponsor|unable to sponsor", req["evidence"], re.I
            ):
                failures.append("Posting excludes sponsorship that you require.")
            else:
                unknown.append("Confirm work authorization against the original requirement.")
        if (
            req["kind"] == "location"
            and hard.get("allow_relocation") is False
            and "relocat" in req["evidence"].lower()
        ):
            unknown.append("Relocation may be required; verify the location.")
    candidate = {alias(s["name"]): s for s in profile.get("skills", [])}
    strong: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    earned = total = 0.0
    for name in sorted({s["name"] for s in extracted["skills"]}):
        rows = [s for s in extracted["skills"] if s["name"] == name]
        obligation = (
            "required"
            if any(s["obligation"] == "required" for s in rows)
            else "preferred"
            if any(s["obligation"] == "preferred" for s in rows)
            else "uncertain"
        )
        weight = 2 if obligation == "required" else 1 if obligation == "preferred" else 0.5
        total += weight
        skill = candidate.get(name)
        if skill:
            evidence = bool(skill.get("evidence") and skill.get("evidence_ref"))
            earned += weight * (1 if evidence else 0.65)
            (strong if evidence else partial).append(
                f"{name}: confirmed profile"
                + (" with linked evidence" if evidence else "; no linked evidence")
            )
        else:
            missing.append(f"{name} ({obligation}; not in confirmed profile)")
    if minimum is not None:
        unknown.append("Professional years are not inferred from projects or ambiguous resume dates.")
    education_required = [
        r for r in extracted["requirements"] if r["kind"] == "education" and r["obligation"] == "required"
    ]
    education_fit = (
        "Review degree subject/level equivalence."
        if education_required
        else "No explicit required education extracted."
    )
    location = 50
    if preferences.get("locations") and data.get("location"):
        location = (
            100 if any(x.casefold() in data["location"].casefold() for x in preferences["locations"]) else 25
        )
    arrangement = 100 if data.get("arrangement") in preferences.get("arrangements", []) else 50
    title_words = set(re.findall(r"[a-z]+", data.get("title", "").lower())) - {
        "junior",
        "senior",
        "entry",
        "level",
        "the",
        "and",
        "i",
    }
    history_words = set(
        re.findall(r"[a-z]+", " ".join(x.get("title", "") for x in profile.get("experience", [])).lower())
    )
    role = (
        round(100 * len(title_words & history_words) / len(title_words))
        if title_words and history_words
        else 50
    )
    degree_text = " ".join(x.get("degree", "") for x in profile.get("education", [])).casefold()
    degree_levels = {
        word
        for word in ("bachelor", "master", "phd")
        if word in " ".join(r["evidence"] for r in education_required).casefold()
    }
    education = 100 if degree_levels and any(word in degree_text for word in degree_levels) else 50
    if education == 100:
        partial.append(
            "Degree level appears in confirmed education; subject/equivalence still requires review."
        )
    parts = dict(
        skills=round(100 * earned / total) if total else 50,
        experience=50,
        role=role,
        education=education,
        location=location,
        preferences=arrangement,
        other=50,
    )
    resume_match = weighted(parts, match_weights or MATCH_WEIGHTS)
    now = at or datetime.now(UTC)
    freshness = 50
    if data.get("posted_at"):
        age = max(0, (now - datetime.fromisoformat(data["posted_at"].replace("Z", "+00:00"))).days)
        freshness = max(0, 100 - age * 3)
    suitability = {
        "NEW_GRAD": 100,
        "TRUE_ENTRY_LEVEL": 100,
        "EARLY_CAREER": 85,
        "REASONABLE_REACH": 60,
        "MID_LEVEL": 20,
        "SENIOR": 0,
        "UNKNOWN": 50,
    }[extracted["early_career"]]
    salary = 50
    if preferences.get("minimum_salary") is not None:
        warnings.append(
            "Salary preference needs matching currency and pay period; no annualization is assumed."
        )
    priority_parts = dict(
        match=resume_match,
        freshness=freshness,
        early_career=suitability,
        location=arrangement,
        salary=salary,
        company=100 if data.get("company") in preferences.get("companies", []) else 50,
        source=50,
    )
    priority = weighted(priority_parts, priority_weights or PRIORITY_WEIGHTS)
    if failures:
        priority = min(priority, 10)
    if extracted["early_career"] in ("MID_LEVEL", "SENIOR"):
        priority = min(priority, 35)
        warnings.append("Posting is outside the early-career target.")
    status = (
        "INELIGIBLE"
        if failures
        else "UNKNOWN"
        if unknown
        else "ELIGIBLE_WITH_WARNING"
        if warnings
        else "ELIGIBLE"
        if data.get("description")
        else "UNKNOWN"
    )
    recommendation = (
        "SKIP"
        if failures
        else "LONG_SHOT"
        if priority < 40
        else "REASONABLE_REACH"
        if priority < 55
        else "APPLY"
        if priority < 70
        else "STRONG_APPLY"
        if priority < 85
        else "EXCELLENT_MATCH"
    )
    return dict(
        **extracted,
        eligibility=status,
        resume_match=resume_match,
        application_priority=priority,
        recommendation=recommendation,
        components=parts,
        priority_components=priority_parts,
        weights=match_weights or MATCH_WEIGHTS,
        priority_weights=priority_weights or PRIORITY_WEIGHTS,
        explanation=dict(
            strong_matches=strong,
            partial_matches=partial,
            missing_qualifications=missing,
            experience_fit="Unknown professional duration; review the source evidence.",
            education_fit=education_fit,
            location_fit="Based only on explicit location/preferences.",
            eligibility_warnings=failures + unknown + warnings,
            recommended_action="Do not apply until conflicts are resolved."
            if failures
            else "Review original requirements and evidence before applying.",
        ),
    )

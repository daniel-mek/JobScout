import re
from datetime import UTC, datetime

from .qualifications import certification_fit, country_code, professional_months
from .qualifications import education_fit as compare_education

VERSION = "rules-2"
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
    section = "uncertain"
    for line in re.split(
        r"[\n.!?](?!\w)|\n",
        "\n".join(
            filter(
                None,
                [
                    data.get("description"),
                    data.get("requirements"),
                    data.get("responsibilities"),
                    data.get("education"),
                    data.get("clearance"),
                    data.get("work_authorization"),
                ],
            )
        ),
    ):
        line = line.strip()[:2000]
        if not line:
            continue
        heading = line.casefold().strip(": •-\t")
        if heading in (
            "requirements",
            "required qualifications",
            "minimum qualifications",
            "qualifications",
            "must have",
        ):
            section = "required"
            continue
        if heading in ("preferred qualifications", "preferred", "nice to have"):
            section = "preferred"
            continue
        if heading in ("responsibilities", "about us", "benefits", "what we offer"):
            section = "uncertain"
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
            else section
        )
        if re.search(r"not (?:strictly )?(?:required|necessary)|no need for", line, re.I):
            obligation = "uncertain"
        if re.search(r"no (?:prior |professional )?experience (?:is )?required|zero years", line, re.I):
            minimum = max(minimum or 0, 0)
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
            value = 0 if re.search(r"up to|at most|maximum", line, re.I) else int(years[1])
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
            "clearance": r"\b(security clearance|secret clearance|top secret)\b",
            "authorization": r"\b(no sponsorship|cannot sponsor|unable to sponsor|authorized to work|work authorization|citizenship required|citizens only)\b",
            "location": r"\b(relocat|on.site|hybrid|remote|must reside)\w*",
        }.items():
            if kind == "clearance" and re.search(
                r"no .{0,15}clearance|clearance (?:is )?not required", line, re.I
            ):
                continue
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
    for field, kind in (
        ("education", "education"),
        ("clearance", "clearance"),
        ("work_authorization", "authorization"),
    ):
        if data.get(field):
            requirements.append(
                dict(
                    kind=kind, value=data[field], obligation="uncertain", evidence=data[field], confidence=0.5
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
    if re.search(r"\b(senior|lead|principal|staff|architect|manager)\b", title):
        level = "SENIOR"
    elif (minimum is None or minimum <= 2) and re.search(
        r"\b(new grad(?:uate)?|recent graduate|rotational program)\b",
        title + "\n" + str(data.get("description", "")),
        re.I,
    ):
        level = "NEW_GRAD"
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
    if data.get("employment_type") == "INTERNSHIP":
        failures.append("Internship postings are outside the current full-time discovery scope.")
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
        if not country_code(data.get("country")):
            unknown.append("Job country is unknown.")
        elif country_code(data["country"]) not in [country_code(x) for x in hard["countries"]]:
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
            elif hard.get("authorized_to_work") is False and re.search(
                r"authorized to work|work authorization", req["evidence"], re.I
            ):
                failures.append("Required work authorization conflicts with your confirmed settings.")
            elif re.search(r"citizenship|citizens only", req["evidence"], re.I):
                unknown.append(
                    "Citizenship is not established by work authorization; verify the original requirement."
                )
            elif hard.get("authorized_to_work") is not True and not (
                hard.get("needs_sponsorship") is False
                and re.search(r"no sponsorship|cannot sponsor|unable to sponsor", req["evidence"], re.I)
            ):
                unknown.append("Confirm work authorization against the original requirement.")
        if (
            req["kind"] == "location"
            and hard.get("allow_relocation") is False
            and "relocat" in req["evidence"].lower()
        ):
            if re.search(r"must relocate|relocation (?:is )?required", req["evidence"], re.I):
                failures.append("Explicit required relocation conflicts with your settings.")
            else:
                unknown.append("Relocation may be required; verify the location.")
    # Absence of a parsed clause is not proof that a constrained requirement is satisfied.
    for kind, constrained in (
        ("clearance", hard.get("allow_clearance") is False),
        (
            "authorization",
            hard.get("needs_sponsorship") is True or hard.get("authorized_to_work") is not None,
        ),
        ("location", hard.get("allow_relocation") is False),
    ):
        if constrained and not any(
            r["kind"] == kind and r["obligation"] == "required" for r in extracted["requirements"]
        ):
            unknown.append(f"No conclusive {kind} requirement extracted; verify the listing.")
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
            ref = skill.get("evidence_ref", "")
            kind, _, index = ref.partition(":")
            entries = profile.get(
                "experience" if kind == "experience" else "projects" if kind == "project" else "invalid", []
            )
            evidence = bool(skill.get("evidence") and index.isdigit() and int(index) < len(entries))
            # Repeated literal mentions in confirmed experience/projects strengthen a linked claim.
            mentions = sum(
                bool(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", x.get("description", ""), re.I))
                for x in profile.get("experience", []) + profile.get("projects", [])
            )
            earned += weight * (min(1, 0.85 + 0.075 * mentions) if evidence else 0.65)
            (strong if evidence else partial).append(
                f"{name}: confirmed profile"
                + (" with linked evidence" if evidence else "; no linked evidence")
            )
        else:
            missing.append(f"{name} ({obligation}; not in confirmed profile)")
    months = professional_months(profile, at)
    experience = (
        50
        if minimum is None or months is None
        else 100
        if minimum == 0
        else min(100, round(months / (minimum * 12) * 100))
    )
    experience_text = (
        "Unknown professional duration; ambiguous dates and internships are not silently converted to years."
    )
    if months is not None:
        experience_text = f"{months} non-overlapping months from explicit dated professional history; projects excluded. Required minimum: {minimum if minimum is not None else 'unknown'} years."
    if minimum is not None and months is None:
        unknown.append("Professional years are not inferred from projects or ambiguous resume dates.")
    elif minimum is not None and experience < 100:
        warnings.append(
            "Confirmed dated professional history falls short of the stated minimum; review transferable experience."
        )
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
            100
            if any(
                re.search(r"(?<!\w)" + re.escape(x.casefold()) + r"(?!\w)", data["location"].casefold())
                for x in preferences["locations"]
                if x.strip()
            )
            else 25
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
    education, education_fit = compare_education(extracted["requirements"], profile)
    if education == 100:
        partial.append(
            "Degree level appears in confirmed education; subject/equivalence still requires review."
        )
    other, certifications_missing = certification_fit(extracted["requirements"], profile)
    missing.extend(
        f"{name} (required certification; absent from confirmed profile)" for name in certifications_missing
    )
    if education == 0:
        missing.append("Required degree level/subject is not established in confirmed education.")
    parts = dict(
        skills=round(100 * earned / total) if total else 50,
        experience=experience,
        role=role,
        education=education,
        location=location,
        preferences=arrangement,
        other=other,
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
        period = str(data.get("salary_period", "")).casefold()
        if (
            data.get("currency") == preferences.get("currency")
            and period in ("year", "yearly", "annual", "per-year", "1 year", "per year", "pa")
            and data.get("salary_min") is not None
        ):
            salary = (
                100
                if data["salary_min"] >= preferences["minimum_salary"]
                else 0
                if data.get("salary_max") is not None and data["salary_max"] < preferences["minimum_salary"]
                else 50
            )
        else:
            warnings.append(
                "Salary comparison is unknown without matching currency and an explicit annual pay period."
            )
    priority_parts = dict(
        match=resume_match,
        freshness=freshness,
        early_career=suitability,
        location=arrangement,
        salary=salary,
        company=100
        if str(data.get("company", "")).casefold() in [x.casefold() for x in preferences.get("companies", [])]
        else 50,
        source=data.get("source_quality", 50),
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
            experience_fit=experience_text,
            education_fit=education_fit,
            location_fit="Based only on explicit location/preferences.",
            eligibility_warnings=failures + unknown + warnings,
            recommended_action="Do not apply until conflicts are resolved."
            if failures
            else "Review original requirements and evidence before applying.",
        ),
    )

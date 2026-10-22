"""Reviewable defaults. Public documentation does not grant storage permission."""

REFERENCES = {
    "greenhouse": ("Greenhouse", "https://docs.greenhouse.io/job-board"),
    "lever": ("Lever", "https://github.com/lever/postings-api"),
    "ashby": ("Ashby", "https://developers.ashbyhq.com/docs/public-job-posting-api"),
    "smartrecruiters": ("SmartRecruiters", "https://developers.smartrecruiters.com/docs/posting-api"),
    "usajobs": ("USAJOBS", "https://developer.usajobs.gov/"),
    "adzuna": ("Adzuna", "https://developer.adzuna.com/docs/search"),
    "remotive": ("Remotive", "https://remotive.com/remote-jobs/api"),
    "workday": ("Workday", "https://www.workday.com/"),
    "generic": ("Company career site", "https://schema.org/JobPosting"),
    "linkedin": ("LinkedIn", "https://www.linkedin.com/legal/user-agreement"),
    "indeed": ("Indeed", "https://www.indeed.com/legal"),
    "ziprecruiter": ("ZipRecruiter", "https://www.ziprecruiter.com/terms"),
    "glassdoor": ("Glassdoor", "https://www.glassdoor.com/about/terms/"),
    "manual": ("Manual import", ""),
}
ADAPTERS = {"greenhouse", "lever", "ashby", "smartrecruiters", "usajobs", "adzuna"}


def defaults():
    for key, (name, docs) in REFERENCES.items():
        manual = key == "manual"
        disabled = key in {"linkedin", "indeed", "ziprecruiter", "glassdoor", "remotive"}
        yield dict(
            id=key,
            display_name=name,
            category="manual" if manual else "api" if key in ADAPTERS else "unsupported",
            documentation_url=docs,
            terms_url="",
            retrieval_method="user_supplied" if manual else "documented_api",
            credentials=["USAJOBS_API_KEY", "USAJOBS_EMAIL"]
            if key == "usajobs"
            else ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"]
            if key == "adzuna"
            else [],
            attribution=name,
            approved_boards=["manual"] if manual else [],
            source_link_required=True,
            rate_limit={"min_interval_seconds": 1, "run_interval_seconds": 300, "max_pages": 4},
            description_storage="allowed" if manual else "unknown",
            redistribution="private_only",
            enabled=manual,
            status="APPROVED" if manual else "DISABLED" if disabled else "NEEDS_REVIEW",
            reviewed_at="2026-10-22" if manual or key == "remotive" else None,
            evidence="User-supplied private records."
            if manual
            else "Public API prohibits signup-gated listings; disabled for this authenticated workspace."
            if key == "remotive"
            else "Technical docs reviewed; storage/usage permission still requires review.",
            adapter_version="1",
            next_run_at=0,
        )

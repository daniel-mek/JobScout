import json
import re
import subprocess
import sys
from typing import Protocol

from fastapi import HTTPException

from .schemas import (
    CertificationInput,
    EducationInput,
    ExperienceInput,
    ProfileData,
    ProjectInput,
    SkillCategory,
    SkillInput,
)


class ResumeTextExtractor(Protocol):
    def extract(self, content: bytes, kind: str) -> str: ...


class IsolatedTextExtractor:
    def extract(self, content: bytes, kind: str) -> str:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "apps.api.applyos.extract_worker", kind],
                input=content,
                capture_output=True,
                timeout=12,
                check=False,
            )
            data = json.loads(result.stdout)
            if result.returncode or "text" not in data:
                raise ValueError("Unsafe document")
            return str(data["text"])
        except (subprocess.TimeoutExpired, ValueError, KeyError):
            raise HTTPException(
                422,
                "Could not extract resume text. Use an unencrypted text-based PDF or DOCX without macros or external links.",
            ) from None


class ResumeParser(Protocol):
    name: str

    def parse(self, text: str) -> ProfileData: ...


SKILLS: dict[SkillCategory, list[str]] = {
    "language": [
        "Python",
        "JavaScript",
        "TypeScript",
        "Java",
        "C++",
        "C#",
        "SQL",
        "Bash",
        "PowerShell",
        "Go",
        "Rust",
    ],
    "framework": ["React", "Next.js", "Django", "FastAPI", ".NET", "Spring"],
    "database": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite"],
    "cloud": ["AWS", "Azure", "GCP"],
    "operating_system": ["Linux", "Windows", "macOS"],
    "tool": ["Docker", "Kubernetes", "Git", "Terraform", "Active Directory", "Jira"],
}
ALIASES = {"JavaScript": ["JS"], "PostgreSQL": ["Postgres"], "AWS": ["Amazon Web Services"]}
SECTIONS = {
    "education": "education",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "internships": "experience",
    "projects": "projects",
    "certifications": "certifications",
    "skills": "skills",
    "technical skills": "skills",
}


class DeterministicResumeParser:
    name = "deterministic-review-required-v1"

    def parse(self, text: str) -> ProfileData:
        """Extract only literal evidence. Grouped blocks require human structuring/review."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        profile = ProfileData()
        if lines and len(lines[0]) <= 100 and not re.search(r"@|https?://|resume|curriculum", lines[0], re.I):
            profile.name = lines[0]
        location = re.search(r"(?im)^Location:\s*(.{1,200})$", text)
        graduation = re.search(r"(?im)^(?:Expected graduation|Graduation(?: date)?):\s*(.{1,80})$", text)
        profile.location = location.group(1).strip() if location else ""
        profile.graduation_date = graduation.group(1).strip() if graduation else ""
        buckets: dict[str, list[str]] = {}
        section = ""
        for line in lines:
            label = line.lower().strip(":")
            if label in SECTIONS:
                section = SECTIONS[label]
            elif section:
                buckets.setdefault(section, []).append(line)
        for kind, blocks in buckets.items():
            block = "\n".join(blocks)
            if kind == "education" and block:
                profile.education.append(EducationInput(institution=blocks[0][:200], evidence=block[:4000]))
            elif kind == "experience" and block:
                profile.experience.append(
                    ExperienceInput(employer="", description=block[:6000], evidence=block[:4000])
                )
            elif kind == "projects" and block:
                profile.projects.append(
                    ProjectInput(name="", description=block[:6000], evidence=block[:4000])
                )
            elif kind == "certifications" and block:
                profile.certifications.append(CertificationInput(name=blocks[0][:200], evidence=block[:4000]))
        evidence_lines = [
            line for block in (profile.experience + profile.projects) for line in block.evidence.splitlines()
        ] + lines
        for category, names in SKILLS.items():
            for name in names:
                variants = [name] + ALIASES.get(name, [])
                evidence = next(
                    (
                        line
                        for line in evidence_lines
                        if any(re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", line, re.I) for v in variants)
                    ),
                    None,
                )
                if evidence:
                    ref = ""
                    if profile.experience and evidence in profile.experience[0].evidence:
                        ref = "experience:0"
                    elif profile.projects and evidence in profile.projects[0].evidence:
                        ref = "project:0"
                    profile.skills.append(
                        SkillInput(
                            name=name,
                            category=category,
                            evidence=evidence[:4000],
                            evidence_ref=ref,
                            confidence=1.0,
                        )
                    )
        return ProfileData.model_validate(profile.model_dump())

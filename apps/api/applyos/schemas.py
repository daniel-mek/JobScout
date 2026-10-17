from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class EducationInput(StrictModel):
    institution: str = Field(max_length=200)
    degree: str = Field(default="", max_length=200)
    graduation_date: str = Field(default="", max_length=80)
    evidence: str = Field(default="", max_length=4000)


class ExperienceInput(StrictModel):
    employer: str = Field(max_length=200)
    title: str = Field(default="", max_length=200)
    dates: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=6000)
    evidence: str = Field(default="", max_length=4000)


class ProjectInput(StrictModel):
    name: str = Field(max_length=200)
    description: str = Field(default="", max_length=6000)
    technologies: str = Field(default="", max_length=500)
    evidence: str = Field(default="", max_length=4000)


SkillCategory = Literal["language", "framework", "database", "cloud", "operating_system", "tool", "other"]


class SkillInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    category: SkillCategory = "other"
    evidence: str = Field(default="", max_length=4000)
    evidence_ref: str = Field(default="", max_length=80)
    confidence: float | None = Field(default=None, ge=0, le=1)


class CertificationInput(StrictModel):
    name: str = Field(max_length=200)
    issuer: str = Field(default="", max_length=200)
    date: str = Field(default="", max_length=80)
    evidence: str = Field(default="", max_length=4000)


class ProfileData(StrictModel):
    name: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    graduation_date: str = Field(default="", max_length=80)
    summary: str = Field(default="", max_length=6000)
    education: list[EducationInput] = Field(default_factory=list, max_length=30)
    experience: list[ExperienceInput] = Field(default_factory=list, max_length=40)
    projects: list[ProjectInput] = Field(default_factory=list, max_length=40)
    skills: list[SkillInput] = Field(default_factory=list, max_length=150)
    certifications: list[CertificationInput] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def evidence_refs(self) -> "ProfileData":
        for skill in self.skills:
            if skill.evidence_ref:
                kind, _, index = skill.evidence_ref.partition(":")
                records = (
                    self.experience if kind == "experience" else self.projects if kind == "project" else []
                )
                if not index.isdigit() or int(index) >= len(records):
                    raise ValueError("Skill evidence reference must identify an experience or project")
        if len({s.name.casefold() for s in self.skills}) != len(self.skills):
            raise ValueError("Skills must be unique")
        return self


class ProfileReview(StrictModel):
    expected_revision: int = Field(ge=0)
    resume_version_id: str
    profile: ProfileData
    confirmed: Literal[True]


class CareerSelection(StrictModel):
    role_ids: list[str] = Field(min_length=1, max_length=20)


class Preferences(StrictModel):
    locations: list[str] = Field(default_factory=list, max_length=20)
    arrangements: list[Literal["REMOTE", "HYBRID", "ONSITE"]] = Field(default_factory=list, max_length=3)
    minimum_salary: int | None = Field(default=None, ge=0, le=10000000)
    currency: Literal["USD", "CAD", "EUR", "GBP"] = "USD"
    industries: list[str] = Field(default_factory=list, max_length=20)
    companies: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def bounded_text(self) -> "Preferences":
        if any(len(x) > 200 for x in self.locations + self.industries + self.companies):
            raise ValueError("Preference values must be at most 200 characters")
        return self


class Requirements(StrictModel):
    max_requested_experience: int | None = Field(default=None, ge=0, le=50)
    allow_clearance: bool | None = None
    allow_contract: bool | None = None
    allow_relocation: bool | None = None
    countries: list[str] = Field(default_factory=list, max_length=20)
    needs_sponsorship: bool | None = None
    authorized_to_work: bool | None = None

    @model_validator(mode="after")
    def country_codes(self) -> "Requirements":
        if any(len(c) != 2 or not c.isalpha() or c != c.upper() for c in self.countries):
            raise ValueError("Countries must be uppercase two-letter codes")
        return self

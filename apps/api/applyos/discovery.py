from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, case, func, or_, select

from packages.matching.engine import VERSION

from .discovery_models import JobReview, Notification, NotificationPreference
from .jobs_models import Company, JobPosting, JobSource, JobSourceRecord
from .jobs_service import JobService, owner_lock
from .match_models import JobMatch
from .models import CandidateProfile, now

KINDS = {
    "NEW_HIGH_MATCH_JOB",
    "FRESH_OPPORTUNITY",
    "SAVED_SEARCH_COMPLETE",
    "FOLLOWED_COMPANY_JOB",
    "APPLICATION_REMINDER",
    "ASSESSMENT_DEADLINE",
    "INTERVIEW_REMINDER",
    "EMAIL_STATUS_SUGGESTION",
}


class Filters(BaseModel):
    view: Literal["for_you", "fresh", "excellent", "reach", "recent"] = "for_you"
    title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    arrangement: str = Field(default="", max_length=30)
    employment_type: str = Field(default="", max_length=60)
    role_family: str = Field(default="", max_length=60)
    source: str = Field(default="", max_length=60)
    recommendation: str = Field(default="", max_length=40)
    early_career: str = Field(default="", max_length=40)
    min_match: int = Field(default=0, ge=0, le=100)
    min_priority: int = Field(default=0, ge=0, le=100)
    min_salary: int | None = Field(default=None, ge=0, le=10000000)
    currency: str = Field(default="USD", max_length=3)
    freshness_days: int | None = Field(default=None, ge=0, le=365)
    saved: bool | None = None
    reviewed: bool | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=25, ge=1, le=100)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    saved: bool | None = None
    reviewed: bool | None = None
    notes: str | None = Field(default=None, max_length=6000)
    deadline: str | None = Field(default=None, max_length=10)
    feedback: Literal["INTERESTED", "NOT_INTERESTED", "CLEAR"] | None = None
    reason: (
        Literal[
            "TOO_FAR",
            "WRONG_ROLE",
            "TOO_SENIOR",
            "SALARY_TOO_LOW",
            "CONTRACT",
            "CLEARANCE_REQUIRED",
            "COMPANY",
            "INDUSTRY",
            "ALREADY_APPLIED",
            "OTHER",
        ]
        | None
    ) = None

    @field_validator("deadline")
    @classmethod
    def valid_date(cls, value):
        if value:
            return date.fromisoformat(value).isoformat()
        return None


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    filters: Filters = Field(default_factory=Filters)


def review_job(db, owner, key, data):
    owner_lock(db, owner)
    job = JobService(db, owner).owned(JobPosting, key)
    row = db.get(JobReview, (owner, key))
    if row is None:
        row = JobReview(owner_id=owner, job_id=key, job_revision=job.revision)
        db.add(row)
    for field in data.model_fields_set:
        value = getattr(data, field)
        if field == "saved" and value is not None:
            if value and not row.saved:
                row.saved_at, row.job_revision = now(), job.revision
            row.saved = value
            if value:
                row.reviewed = True
        elif field == "feedback" and value:
            row.feedback = None if value == "CLEAR" else value
            row.reason = data.reason if value == "NOT_INTERESTED" else None
            if value != "CLEAR":
                row.reviewed = True
        elif field == "notes" and value is not None:
            row.notes = value
        elif field == "deadline":
            row.deadline = value
        elif field == "reviewed" and value is not None:
            row.reviewed = value
        elif field == "reason" and row.feedback == "NOT_INTERESTED":
            row.reason = value
    if data.saved is True or data.feedback in ("INTERESTED", "NOT_INTERESTED"):
        row.reviewed = True
    db.commit()
    return review_view(row)


def review_view(row):
    return dict(
        saved=row.saved,
        saved_at=row.saved_at,
        reviewed=row.reviewed,
        notes=row.notes,
        deadline=row.deadline,
        feedback=row.feedback,
        reason=row.reason,
        job_revision=row.job_revision,
    )


def discover(db, owner, filters):
    ranked = (
        select(
            JobMatch.id.label("id"),
            func.row_number()
            .over(partition_by=JobMatch.job_id, order_by=(JobMatch.calculated_at.desc(), JobMatch.id.desc()))
            .label("rank"),
        )
        .where(JobMatch.owner_id == owner)
        .subquery()
    )
    latest = select(JobMatch).join(ranked, ranked.c.id == JobMatch.id).where(ranked.c.rank == 1).subquery()
    from sqlalchemy.orm import aliased

    match = aliased(JobMatch, latest)
    query = (
        select(JobPosting, match, JobReview)
        .join(Company, Company.id == JobPosting.company_id)
        .outerjoin(
            match,
            and_(
                match.job_id == JobPosting.id,
                match.job_revision == JobPosting.revision,
                match.algorithm_version == VERSION,
            ),
        )
        .outerjoin(JobReview, and_(JobReview.job_id == JobPosting.id, JobReview.owner_id == owner))
        .where(JobPosting.owner_id == owner)
    )
    if filters.saved is not True:
        query = query.where(
            JobPosting.active.is_(True),
            or_(JobReview.feedback.is_(None), JobReview.feedback != "NOT_INTERESTED"),
        )
    for field, column in (
        ("title", JobPosting.title),
        ("company", Company.name),
        ("location", JobPosting.location),
    ):
        value = getattr(filters, field)
        if value:
            query = query.where(func.lower(column).contains(value.lower(), autoescape=True))
    for field, column in (
        ("arrangement", JobPosting.arrangement),
        ("employment_type", JobPosting.employment_type),
    ):
        if getattr(filters, field):
            query = query.where(column == getattr(filters, field))
    if filters.role_family:
        from .models import RoleFamily

        role = db.get(RoleFamily, filters.role_family)
        if role is None:
            raise HTTPException(422, "Unknown role family")
        words = [x for x in role.name.lower().replace("/", " ").split() if len(x) >= 2]
        words += [word[:-3] for word in words if word.endswith("ing")]
        query = query.where(
            or_(*(func.lower(JobPosting.title).contains(word, autoescape=True) for word in words))
        )
    for field, flag_column in (("saved", JobReview.saved), ("reviewed", JobReview.reviewed)):
        value = getattr(filters, field)
        if value is not None:
            query = query.where(func.coalesce(flag_column, False) == value)
    if filters.source:
        query = query.where(
            JobPosting.id.in_(
                select(JobSourceRecord.job_id)
                .join(JobSource)
                .where(JobSource.policy_id == filters.source, JobSource.owner_id == owner)
            )
        )
    if filters.min_salary is not None:
        query = query.where(
            JobPosting.data["salary_min"].as_float() >= filters.min_salary,
            JobPosting.data["currency"].as_string() == filters.currency,
            JobPosting.data["salary_period"]
            .as_string()
            .in_(["year", "yearly", "annual", "per-year", "1 YEAR", "per year"]),
        )
    for field, key in (("recommendation", "recommendation"), ("early_career", "early_career")):
        if getattr(filters, field):
            query = query.where(match.result[key].as_string() == getattr(filters, field))
    for field, key in (("min_match", "resume_match"), ("min_priority", "application_priority")):
        if getattr(filters, field):
            query = query.where(match.result[key].as_integer() >= getattr(filters, field))
    days = (
        filters.freshness_days
        if filters.freshness_days is not None
        else 7
        if filters.view == "fresh"
        else None
    )
    if days is not None:
        query = query.where(JobPosting.posted_at >= (datetime.now(UTC) - timedelta(days=days)).isoformat())
    if filters.view == "excellent":
        query = query.where(match.result["recommendation"].as_string() == "EXCELLENT_MATCH")
    if filters.view == "reach":
        query = query.where(match.result["recommendation"].as_string() == "REASONABLE_REACH")
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    # Explicit positive feedback is only a small tie-breaking preference; never a hard requirement.
    score = match.result["application_priority"].as_integer()
    order = (
        (JobPosting.discovered_at.desc(), JobPosting.id)
        if filters.view == "recent"
        else (
            score.desc().nullslast(),
            case((JobReview.feedback == "INTERESTED", 1), else_=0).desc(),
            JobPosting.discovered_at.desc(),
            JobPosting.id,
        )
    )
    rows = db.execute(query.order_by(*order).offset(filters.offset).limit(filters.limit)).all()
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.owner_id == owner))
    return dict(
        total=total,
        as_of=now(),
        offset=filters.offset,
        items=[
            dict(
                **JobService(db, owner).summary(job),
                salary_min=job.data.get("salary_min"),
                salary_max=job.data.get("salary_max"),
                currency=job.data.get("currency"),
                salary_period=job.data.get("salary_period"),
                match=record.result if record else None,
                match_calculated_at=record.calculated_at if record else None,
                match_profile_revision=record.profile_revision if record else None,
                match_profile_current=bool(
                    record and profile and record.profile_revision == profile.revision
                ),
                review=review_view(review) if review else None,
            )
            for job, record, review in rows
        ],
    )


def notify(db, owner, event_key, kind, job_id=None):
    preference = db.get(NotificationPreference, owner)
    if preference and kind in preference.disabled_types:
        return
    if db.scalar(
        select(Notification.id).where(Notification.owner_id == owner, Notification.event_key == event_key)
    ):
        return
    db.add(Notification(owner_id=owner, event_key=event_key, kind=kind, job_id=job_id))


def daily_brief(db, owner):
    # Cached, bounded matches only: no foreground bulk calculation or filler jobs.
    items = discover(db, owner, Filters(limit=100))["items"]
    today = datetime.now(UTC).date().isoformat()
    new = [x for x in items if x["discovered_at"][:10] == today]
    return dict(
        date=today,
        sections={
            "excellent": [x for x in new if x["match"] and x["match"]["recommendation"] == "EXCELLENT_MATCH"],
            "strong_apply": [x for x in new if x["match"] and x["match"]["recommendation"] == "STRONG_APPLY"],
            "fresh_reach": [
                x
                for x in new
                if x["match"]
                and x["match"]["recommendation"] == "REASONABLE_REACH"
                and x["posted_at"]
                and x["posted_at"] >= (datetime.now(UTC) - timedelta(days=7)).isoformat()
            ],
            "needs_review": [x for x in new if not x["match"] or x["match"]["eligibility"] == "UNKNOWN"],
        },
        notice="Up to 100 highest-priority active jobs evaluated; unknown and empty sections remain explicit.",
    )

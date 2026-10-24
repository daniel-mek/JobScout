import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select

from packages.matching.engine import MATCH_WEIGHTS, PRIORITY_WEIGHTS, VERSION, calculate

from .jobs_models import JobPosting, JobSource, SourcePolicy
from .jobs_service import JobService, owner_lock
from .match_models import JobMatch, JobRequirement, JobSkill, ScoringPolicy
from .models import CareerPreference, HardRequirement, JobSearchPreference
from .services import ProfileService


def match_job(db, owner, key):
    owner_lock(db, owner)
    job = JobService(db, owner).owned(JobPosting, key)
    profile = ProfileService(db, owner).current()
    if not profile["profile"]:
        raise HTTPException(409, "Review and confirm your profile before calculating a match.")
    preferences = db.get(JobSearchPreference, owner)
    hard = db.get(HardRequirement, owner)
    policy = policy_for(db, owner)
    source = db.get(JobSource, job.content_source_id)
    source_policy = db.get(SourcePolicy, source.policy_id)
    quality = (
        100
        if source_policy.enabled
        and source_policy.status == "APPROVED"
        and source.policy_id in ("greenhouse", "lever", "ashby", "smartrecruiters")
        else 50
    )
    # Daily freshness invalidation is independent of all content revisions.
    inputs = dict(
        job=job.data,
        active=job.active,
        revision=job.revision,
        profile=profile,
        preferences=preferences.data if preferences else {},
        hard=hard.data if hard else {},
        algorithm=VERSION,
        scoring_policy=policy,
        source_quality=quality,
        career_roles=sorted(
            db.scalars(select(CareerPreference.role_family_id).where(CareerPreference.owner_id == owner))
        ),
        day=datetime.now(UTC).date().isoformat(),
    )
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(
        select(JobMatch).where(
            JobMatch.owner_id == owner, JobMatch.job_id == key, JobMatch.input_hash == digest
        )
    )
    if existing:
        return view(existing)
    result = calculate(
        {**job.data, "active": job.active, "source_quality": quality},
        profile["profile"],
        inputs["preferences"],
        inputs["hard"],
        match_weights=policy["weights"],
        priority_weights=policy["priority_weights"],
    )
    for model, field in ((JobRequirement, "requirements"), (JobSkill, "skills")):
        db.execute(delete(model).where(model.job_id == key))
        for data in result[field]:
            db.add(model(job_id=key, job_revision=job.revision, data=data))
    row = JobMatch(
        owner_id=owner,
        job_id=key,
        input_hash=digest,
        profile_revision=profile["revision"],
        resume_version_id=profile.get("resume_version_id"),
        job_revision=job.revision,
        algorithm_version=VERSION,
        result=result,
    )
    db.add(row)
    db.commit()
    return view(row)


def view(row):
    return dict(
        id=row.id,
        profile_revision=row.profile_revision,
        resume_version_id=row.resume_version_id,
        job_revision=row.job_revision,
        algorithm_version=row.algorithm_version,
        calculated_at=row.calculated_at,
        result=row.result,
    )


def policy_for(db, owner):
    row = db.get(ScoringPolicy, owner)
    return (
        dict(revision=row.revision, weights=row.weights, priority_weights=row.priority_weights)
        if row
        else dict(revision=0, weights=MATCH_WEIGHTS, priority_weights=PRIORITY_WEIGHTS)
    )

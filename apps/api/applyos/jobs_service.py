import hashlib
import json
import re
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from packages.job_sources import adapters
from packages.job_sources.adapters import Posting, normalized
from packages.job_sources.catalog import ADAPTERS
from packages.job_sources.registry import SourceRegistry
from packages.job_sources.safe_http import SourceError

from .config import Settings, settings
from .jobs_models import (
    Company,
    JobPosting,
    JobPostingVersion,
    JobSource,
    JobSourceRecord,
    SearchRun,
    SourceHealth,
    SourcePolicy,
)
from .models import now

CONTENT = {
    "description",
    "responsibilities",
    "requirements",
    "education",
    "clearance",
    "work_authorization",
    "experience_min",
    "experience_max",
}


def permitted(data: dict, policy: SourcePolicy) -> dict:
    result = dict(data)
    if policy.description_storage != "allowed":
        for key in CONTENT:
            result[key] = None
    return result


def fingerprint(data: dict) -> str:
    # Provider dates and retrieval clocks alone must not create versions.
    stable = {k: v for k, v in data.items() if k not in ("posted_at", "external_id")}
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def owner_lock(db: Session, owner: str):
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        number = int.from_bytes(hashlib.sha256(("jobs:" + owner).encode()).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": number})


def sanitize_policy_history(db: Session, policy: SourcePolicy):
    """Purge restricted content across live records and every historical version."""
    if policy.description_storage == "allowed":
        return
    source_ids = select(JobSource.id).where(JobSource.policy_id == policy.id)
    from .application_models import ApplicationSnapshot

    for snapshot in db.scalars(
        select(ApplicationSnapshot).where(ApplicationSnapshot.source_id.in_(source_ids))
    ):
        snapshot.data = permitted(snapshot.data, policy)
        snapshot.match = None
        snapshot.restriction = "Archived content removed to honor the current source storage policy."
    from sqlalchemy import delete

    from .match_models import JobMatch, JobRequirement, JobSkill

    affected_jobs = select(JobSourceRecord.job_id).where(JobSourceRecord.source_id.in_(source_ids))
    for model in (JobMatch, JobRequirement, JobSkill):
        db.execute(delete(model).where(model.job_id.in_(affected_jobs)))
    for record in db.scalars(select(JobSourceRecord).where(JobSourceRecord.source_id.in_(source_ids))):
        record.normalized_data = permitted(record.normalized_data, policy)
    for version in db.scalars(select(JobPostingVersion).where(JobPostingVersion.source_id.in_(source_ids))):
        version.data = permitted(version.data, policy)
    for job in db.scalars(select(JobPosting).where(JobPosting.content_source_id.in_(source_ids))):
        job.data = permitted(job.data, policy)
        job.fingerprint = fingerprint(job.data)
    db.flush()


class JobService:
    def __init__(self, db: Session, owner: str, config: Settings | None = None):
        self.db, self.owner = db, owner
        self.credentials = {
            key: getattr(config or settings(), key.lower()).get_secret_value()
            for key in ("USAJOBS_API_KEY", "USAJOBS_EMAIL", "ADZUNA_APP_ID", "ADZUNA_APP_KEY")
        }

    def owned(self, model, key):
        row = self.db.scalar(select(model).where(model.id == key, model.owner_id == self.owner))
        if row is None:
            raise HTTPException(404, "Record not found.")
        return row

    def sources(self):
        rows = self.db.scalars(
            select(JobSource).where(JobSource.owner_id == self.owner).order_by(JobSource.company_name)
        )
        return [self.source_view(row) for row in rows]

    def source_view(self, row):
        policy = self.db.get(SourcePolicy, row.policy_id)
        health = self.db.get(SourceHealth, row.id)
        assert policy is not None and health is not None
        return {
            "id": row.id,
            "provider": row.policy_id,
            "company": row.company_name,
            "board": row.board,
            "url": row.url,
            "enabled": row.enabled,
            "policy_status": policy.status,
            "health": {
                "state": health.state,
                "code": health.code,
                "last_success": health.last_success,
                "last_failure": health.last_failure,
                "next_run_at": max(health.next_run_at, policy.next_run_at),
                "last_count": health.last_count,
            },
        }

    def create_source(self, provider, board, company, url):
        owner_lock(self.db, self.owner)
        if provider not in ADAPTERS:
            raise HTTPException(422, "This source supports manual import only.")
        if not re.fullmatch(r"(?:eu:)?[A-Za-z0-9_-]{1,100}", board):
            raise HTTPException(422, "Use the public board identifier or one search keyword.")
        if url and provider in {"greenhouse", "lever", "ashby", "smartrecruiters"}:
            found = adapters.detect(url)
            if found["provider"] != provider or found["board"] != board:
                raise HTTPException(422, "The career URL does not match this provider and board.")
        existing = self.db.scalar(
            select(JobSource).where(
                JobSource.owner_id == self.owner, JobSource.policy_id == provider, JobSource.board == board
            )
        )
        if existing:
            return self.source_view(existing)
        row = JobSource(owner_id=self.owner, policy_id=provider, board=board, company_name=company, url=url)
        self.db.add(row)
        self.db.flush()
        self.db.add(SourceHealth(source_id=row.id, state="policy_review", code="not_run"))
        self.db.commit()
        return self.source_view(row)

    def manual(self, posting: Posting):
        owner_lock(self.db, self.owner)
        source = self.db.scalar(
            select(JobSource).where(JobSource.owner_id == self.owner, JobSource.policy_id == "manual")
        )
        if source is None:
            source = JobSource(
                owner_id=self.owner, policy_id="manual", company_name="Manual imports", board="manual", url=""
            )
            self.db.add(source)
            self.db.flush()
            self.db.add(SourceHealth(source_id=source.id, state="healthy", code="user_supplied"))
        policy = self.db.get(SourcePolicy, "manual")
        assert policy is not None
        posting.external_id = hashlib.sha256(posting.application_url.encode()).hexdigest()
        job = self.ingest(source, policy, posting)
        self.db.commit()
        return self.detail(job.id)

    def ingest(self, source: JobSource, policy: SourcePolicy, posting: Posting):
        data = permitted(posting.model_dump(), policy)
        record = self.db.scalar(
            select(JobSourceRecord).where(
                JobSourceRecord.source_id == source.id, JobSourceRecord.external_id == posting.external_id
            )
        )
        job = self.db.get(JobPosting, record.job_id) if record else None
        if job is None:
            job = self.db.scalar(
                select(JobPosting).where(
                    JobPosting.owner_id == self.owner, JobPosting.canonical_url == posting.application_url
                )
            )
        company_key = normalized(posting.company)
        company = self.db.scalar(
            select(Company).where(Company.owner_id == self.owner, Company.normalized_name == company_key)
        )
        if company is None:
            company = Company(owner_id=self.owner, name=posting.company, normalized_name=company_key)
            self.db.add(company)
            self.db.flush()
        if job is None and data.get("description") and len(data["description"]) >= 200 and posting.posted_at:
            # Conservative exact-content equivalence, never title-only similarity.
            candidates = self.db.scalars(
                select(JobPosting).where(
                    JobPosting.owner_id == self.owner,
                    JobPosting.company_id == company.id,
                    JobPosting.normalized_title == normalized(posting.title),
                    JobPosting.location == posting.location,
                )
            )
            for candidate in candidates:
                if candidate.posted_at and candidate.data.get("description") == data["description"]:
                    days = (
                        abs(
                            (
                                datetime.fromisoformat(candidate.posted_at)
                                - datetime.fromisoformat(posting.posted_at)
                            ).total_seconds()
                        )
                        / 86400
                    )
                    if days <= 7:
                        job = candidate
                        break
        timestamp = now()
        is_new = job is None
        if job is None:
            job = JobPosting(
                owner_id=self.owner,
                company_id=company.id,
                title=posting.title,
                normalized_title=normalized(posting.title),
                canonical_url=posting.application_url,
                content_source_id=source.id,
                data=data,
                fingerprint="",
                revision=0,
            )
            self.db.add(job)
            self.db.flush()
        if record is None:
            record = JobSourceRecord(
                source_id=source.id,
                job_id=job.id,
                external_id=posting.external_id,
                source_url=posting.application_url,
                normalized_data=data,
            )
            self.db.add(record)
        record.source_url, record.normalized_data = posting.application_url, data
        record.posted_at, record.last_seen_at, record.retrieved_at, record.active = (
            posting.posted_at,
            timestamp,
            timestamp,
            True,
        )
        # Prefer verified ATS destinations to aggregator redirects, without inventing links.
        existing_source = self.db.get(JobSource, job.content_source_id)
        assert existing_source is not None
        prefer = source.policy_id in {
            "greenhouse",
            "lever",
            "ashby",
            "smartrecruiters",
        } and existing_source.policy_id in {"adzuna", "usajobs"}
        if is_new or source.id == job.content_source_id or prefer:
            # Keep a canonical URL when conservative content equivalence merged sources.
            if not prefer:
                data["application_url"] = job.canonical_url
            else:
                job.canonical_url = posting.application_url
            if job.fingerprint != fingerprint(data) or not job.active:
                job.revision += 1
                job.company_id, job.title, job.normalized_title = (
                    company.id,
                    posting.title,
                    normalized(posting.title),
                )
                job.location, job.country = posting.location, posting.country
                job.arrangement, job.employment_type = posting.arrangement, posting.employment_type
                job.data, job.fingerprint, job.content_source_id = data, fingerprint(data), source.id
                self.db.add(
                    JobPostingVersion(
                        job_id=job.id,
                        source_id=source.id,
                        version=job.revision,
                        data={**data, "active": True},
                    )
                )
        job.posted_at = posting.posted_at or job.posted_at
        job.active, job.last_seen_at = True, timestamp
        self.db.flush()
        return job

    def run(self, source_ids: list[str], search_id=None):
        owner_lock(self.db, self.owner)
        sources = [self.owned(JobSource, key) for key in source_ids]
        sources.sort(key=lambda source: (source.policy_id, source.id))
        run = SearchRun(owner_id=self.owner, saved_search_id=search_id, results=[])
        self.db.add(run)
        self.db.flush()
        results = []
        for source in sources:
            # Row lock serializes provider/employer traffic across processes/users in PostgreSQL.
            policy = self.db.scalar(
                select(SourcePolicy).where(SourcePolicy.id == source.policy_id).with_for_update()
            )
            health = self.db.get(SourceHealth, source.id)
            assert policy is not None and health is not None
            epoch = int(time.time())
            missing = [key for key in policy.credentials if not self.credentials.get(key)]
            if missing:
                state, code = "configuration_required", "missing_credentials"
            elif not source.enabled or not policy.enabled or policy.status != "APPROVED":
                state, code = "policy_review", "source_not_approved"
            elif source.board not in policy.approved_boards and "*" not in policy.approved_boards:
                state, code = "policy_review", "board_not_approved"
            elif source.policy_id not in ADAPTERS:
                state, code = "unavailable", "adapter_unavailable"
            elif max(policy.next_run_at, health.next_run_at) > epoch:
                state, code = "degraded", "cooldown"
            else:
                try:
                    cycle_start = now() if source.cursor == 0 else health.cycle_started_at
                    # Fetch/validate the whole bounded response before changing any job rows.
                    rows, complete, next_cursor = SourceRegistry.get(source.policy_id).search(
                        source.board,
                        source.company_name,
                        {key: self.credentials[key] for key in policy.credentials},
                        policy.rate_limit,
                        cursor=source.cursor,
                    )
                    for posting in rows:
                        self.ingest(source, policy, posting)
                    health.cycle_started_at = cycle_start
                    if complete:
                        self.archive_missing(source, cycle_start)
                    source.cursor = next_cursor
                    health.last_count, health.last_success, health.failures = len(rows), now(), 0
                    state, code = ("healthy", "complete") if complete else ("degraded", "partial_feed")
                except (SourceError, ValueError, TypeError, KeyError, AttributeError) as error:
                    state = (
                        "degraded"
                        if isinstance(error, SourceError) and error.code == "rate_limited"
                        else "unavailable"
                    )
                    code = error.code if isinstance(error, SourceError) else "invalid_response"
                    health.last_failure, health.failures = now(), health.failures + 1
                    health.next_run_at = epoch + max(
                        min(3600, 30 * 2 ** min(health.failures, 6)),
                        error.retry_after if isinstance(error, SourceError) else 0,
                    )
                finished = int(time.time())
                policy.next_run_at = finished + max(1, int(policy.rate_limit.get("min_interval_seconds", 1)))
                health.next_run_at = max(
                    health.next_run_at,
                    finished + max(60, int(policy.rate_limit.get("run_interval_seconds", 300))),
                )
            health.state, health.code = state, code
            results.append(
                {
                    "source_id": source.id,
                    "state": state,
                    "code": code,
                    "count": health.last_count if code in ("complete", "partial_feed") else 0,
                }
            )
        run.results, run.finished_at = results, now()
        run.state = "complete" if all(x["code"] == "complete" for x in results) else "partial"
        if search_id:
            from .discovery import notify

            notify(self.db, self.owner, "search:" + run.id, "SAVED_SEARCH_COMPLETE")
        self.db.commit()
        return self.run_view(run)

    def archive_missing(self, source, cycle_start):
        records = list(self.db.scalars(select(JobSourceRecord).where(JobSourceRecord.source_id == source.id)))
        affected = set()
        for record in records:
            if cycle_start and record.last_seen_at < cycle_start and record.active:
                record.active = False
                affected.add(record.job_id)
        self.db.flush()
        for job_id in affected:
            active = self.db.scalar(
                select(JobSourceRecord.id)
                .where(JobSourceRecord.job_id == job_id, JobSourceRecord.active.is_(True))
                .limit(1)
            )
            job = self.db.get(JobPosting, job_id)
            assert job is not None
            if not active and job.active:
                job.active = False
                job.revision += 1
                self.db.add(
                    JobPostingVersion(
                        job_id=job.id,
                        source_id=job.content_source_id,
                        version=job.revision,
                        data={**job.data, "active": False},
                    )
                )

    def summary(self, job):
        company = self.db.get(Company, job.company_id)
        assert company is not None
        sources = self.db.execute(
            select(SourcePolicy.attribution, JobSourceRecord.source_url)
            .join(JobSource, JobSource.policy_id == SourcePolicy.id)
            .join(JobSourceRecord, JobSourceRecord.source_id == JobSource.id)
            .where(JobSourceRecord.job_id == job.id)
        ).all()
        return {
            "id": job.id,
            "title": job.title,
            "company": company.name,
            "location": job.location,
            "country": job.country,
            "arrangement": job.arrangement,
            "employment_type": job.employment_type,
            "application_url": job.canonical_url,
            "active": job.active,
            "posted_at": job.posted_at,
            "discovered_at": job.discovered_at,
            "last_seen_at": job.last_seen_at,
            "revision": job.revision,
            "sources": [{"attribution": label, "url": url} for label, url in sources],
        }

    def detail(self, key):
        job = self.owned(JobPosting, key)
        records = self.db.scalars(select(JobSourceRecord).where(JobSourceRecord.job_id == job.id))
        provenance = []
        for record in records:
            source = self.db.get(JobSource, record.source_id)
            assert source is not None
            policy = self.db.get(SourcePolicy, source.policy_id)
            assert policy is not None
            provenance.append(
                {
                    "provider": policy.id,
                    "attribution": policy.attribution,
                    "source_url": record.source_url,
                    "external_id": record.external_id,
                    "retrieved_at": record.retrieved_at,
                    "posted_at": record.posted_at,
                    "last_seen_at": record.last_seen_at,
                    "active": record.active,
                    "description_storage": policy.description_storage,
                }
            )
        versions = list(
            self.db.scalars(
                select(JobPostingVersion)
                .where(JobPostingVersion.job_id == job.id)
                .order_by(JobPostingVersion.version.desc())
            )
        )
        return {
            **self.summary(job),
            "data": job.data,
            "provenance": provenance,
            "versions": [
                {"version": v.version, "created_at": v.created_at, "data": v.data} for v in versions
            ],
        }

    @staticmethod
    def run_view(run):
        return {
            "id": run.id,
            "state": run.state,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "results": run.results,
        }

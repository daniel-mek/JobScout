from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.job_sources.adapters import Posting, detect
from packages.job_sources.catalog import ADAPTERS
from packages.job_sources.safe_http import SourceError, public_url

from .jobs_models import JobPosting, JobSource, SavedSearch, SearchRun, SearchTitle, SourcePolicy
from .jobs_service import JobService
from .models import User


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class URLInput(Input):
    url: str = Field(min_length=1, max_length=2000)

    @field_validator("url")
    @classmethod
    def safe(cls, value):
        try:
            return public_url(value)
        except SourceError:
            raise ValueError("Use a public HTTP or HTTPS URL.") from None


class SourceInput(Input):
    provider: Literal["greenhouse", "lever", "ashby", "smartrecruiters", "usajobs", "adzuna"]
    board: str = Field(min_length=1, max_length=100)
    company: str = Field(min_length=1, max_length=200)
    url: str = Field(default="", max_length=2000)

    @field_validator("url")
    @classmethod
    def safe(cls, value):
        return URLInput(url=value).url if value else ""


class ManualInput(Posting):
    external_id: str = "manual"


class RunInput(Input):
    source_ids: list[str] = Field(min_length=1, max_length=3)


class SavedSearchInput(RunInput):
    name: str = Field(min_length=1, max_length=120)


class TitleInput(Input):
    title: str = Field(min_length=1, max_length=200)


def router_for(database, current_user, config):
    router = APIRouter()
    DB = Annotated[Session, Depends(database)]
    Current = Annotated[User, Depends(current_user)]

    @router.get("/source-registry")
    def registry(db: DB, user: Current):
        rows = db.scalars(select(SourcePolicy).order_by(SourcePolicy.display_name))
        return [
            {
                key: getattr(row, key)
                for key in (
                    "id",
                    "display_name",
                    "category",
                    "documentation_url",
                    "terms_url",
                    "retrieval_method",
                    "credentials",
                    "approved_boards",
                    "attribution",
                    "source_link_required",
                    "rate_limit",
                    "description_storage",
                    "redistribution",
                    "enabled",
                    "status",
                    "reviewed_at",
                    "evidence",
                    "adapter_version",
                )
            }
            | {"adapter_available": row.id in ADAPTERS}
            for row in rows
        ]

    @router.post("/career-sites/detect")
    def detection(data: URLInput, user: Current):
        return detect(data.url)

    @router.get("/sources")
    def sources(db: DB, user: Current):
        return JobService(db, user.id, config).sources()

    @router.post("/sources", status_code=201)
    def add_source(data: SourceInput, db: DB, user: Current):
        return JobService(db, user.id, config).create_source(
            data.provider, data.board, data.company, data.url
        )

    @router.patch("/sources/{key}")
    def toggle_source(key: str, enabled: bool, db: DB, user: Current):
        service = JobService(db, user.id, config)
        source = service.owned(JobSource, key)
        source.enabled = enabled
        db.commit()
        return service.source_view(source)

    @router.post("/search-runs", status_code=201)
    def run(data: RunInput, db: DB, user: Current):
        return JobService(db, user.id, config).run(list(dict.fromkeys(data.source_ids)))

    @router.get("/search-runs")
    def runs(db: DB, user: Current):
        rows = db.scalars(
            select(SearchRun)
            .where(SearchRun.owner_id == user.id)
            .order_by(SearchRun.started_at.desc())
            .limit(30)
        )
        return [JobService.run_view(row) for row in rows]

    @router.post("/saved-searches", status_code=201)
    def save_search(data: SavedSearchInput, db: DB, user: Current):
        service = JobService(db, user.id, config)
        for key in data.source_ids:
            service.owned(JobSource, key)
        row = SavedSearch(owner_id=user.id, name=data.name, source_ids=list(dict.fromkeys(data.source_ids)))
        db.add(row)
        db.commit()
        return {"id": row.id, "name": row.name, "source_ids": row.source_ids}

    @router.get("/saved-searches")
    def searches(db: DB, user: Current):
        return [
            {"id": row.id, "name": row.name, "source_ids": row.source_ids}
            for row in db.scalars(select(SavedSearch).where(SavedSearch.owner_id == user.id))
        ]

    @router.post("/saved-searches/{key}/run", status_code=201)
    def run_saved(key: str, db: DB, user: Current):
        service = JobService(db, user.id, config)
        row = service.owned(SavedSearch, key)
        return service.run(row.source_ids, row.id)

    @router.get("/search-titles")
    def titles(db: DB, user: Current):
        return [
            {"id": row.id, "title": row.title}
            for row in db.scalars(select(SearchTitle).where(SearchTitle.owner_id == user.id))
        ]

    @router.post("/search-titles", status_code=201)
    def add_title(data: TitleInput, db: DB, user: Current):
        row = SearchTitle(owner_id=user.id, title=data.title)
        db.add(row)
        db.commit()
        return {"id": row.id, "title": row.title}

    @router.post("/jobs/manual", status_code=201)
    def manual(data: ManualInput, db: DB, user: Current):
        return JobService(db, user.id, config).manual(data)

    @router.get("/jobs")
    def jobs(
        db: DB,
        user: Current,
        offset: int = Query(0, ge=0),
        limit: int = Query(30, ge=1, le=100),
        active: bool | None = None,
    ):
        query = select(JobPosting).where(JobPosting.owner_id == user.id)
        if active is not None:
            query = query.where(JobPosting.active == active)
        rows = db.scalars(
            query.order_by(JobPosting.discovered_at.desc(), JobPosting.id).offset(offset).limit(limit)
        )
        return [JobService(db, user.id, config).summary(row) for row in rows]

    @router.get("/jobs/{key}")
    def detail(key: str, db: DB, user: Current):
        return JobService(db, user.id, config).detail(key)

    @router.post("/jobs/import-url", status_code=201)
    def import_url(data: URLInput, db: DB, user: Current):
        # The supplied URL is NEVER fetched. Only registered ATS board endpoints run.
        found = detect(data.url)
        if not found["supported"]:
            return {"status": "manual_required", "reason": found["reason"]}
        service = JobService(db, user.id, config)
        source = db.scalar(
            select(JobSource).where(
                JobSource.owner_id == user.id,
                JobSource.policy_id == found["provider"],
                JobSource.board == found["board"],
            )
        )
        if source is None:
            return {"status": "source_required", "reason": "Add this employer source first.", **found}
        run = service.run([source.id])
        # A link match requires canonical URL or its explicit provider job identifier.
        from urllib.parse import urlsplit

        target = urlsplit(data.url).path.rstrip("/").split("/")[-1]
        for job in db.scalars(select(JobPosting).where(JobPosting.owner_id == user.id)):
            if job.canonical_url == data.url:
                return {"status": "imported", "job_id": job.id}
            if target and target != found["board"]:
                from .jobs_models import JobSourceRecord

                record = db.scalar(
                    select(JobSourceRecord).where(
                        JobSourceRecord.job_id == job.id,
                        JobSourceRecord.source_id == source.id,
                        JobSourceRecord.external_id == target,
                    )
                )
                if record:
                    return {"status": "imported", "job_id": job.id}
        return {
            "status": "manual_required",
            "reason": "Listing not returned by the approved source. Enter details manually.",
            "run": run,
        }

    return router

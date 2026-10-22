from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import now, uid


class SourcePolicy(Base):
    __tablename__ = "source_policies"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(30))
    documentation_url: Mapped[str] = mapped_column(Text)
    terms_url: Mapped[str] = mapped_column(Text)
    retrieval_method: Mapped[str] = mapped_column(String(40))
    credentials: Mapped[list[str]] = mapped_column(JSON)
    approved_boards: Mapped[list[str]] = mapped_column(JSON, default=list)
    attribution: Mapped[str] = mapped_column(String(200))
    source_link_required: Mapped[bool] = mapped_column(Boolean)
    rate_limit: Mapped[dict[str, Any]] = mapped_column(JSON)
    description_storage: Mapped[str] = mapped_column(String(30))
    redistribution: Mapped[str] = mapped_column(String(30))
    enabled: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(30))
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence: Mapped[str] = mapped_column(Text)
    adapter_version: Mapped[str] = mapped_column(String(40))
    next_run_at: Mapped[int] = mapped_column(Integer, default=0)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("owner_id", "normalized_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200))


class JobSource(Base):
    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("owner_id", "policy_id", "board"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("source_policies.id"))
    company_name: Mapped[str] = mapped_column(String(200))
    board: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cursor: Mapped[int] = mapped_column(Integer, default=0)


class SourceHealth(Base):
    __tablename__ = "source_health"
    source_id: Mapped[str] = mapped_column(ForeignKey("job_sources.id", ondelete="CASCADE"), primary_key=True)
    state: Mapped[str] = mapped_column(String(40), default="policy_review")
    last_success: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_failure: Mapped[str | None] = mapped_column(String(40), nullable=True)
    code: Mapped[str] = mapped_column(String(80), default="not_run")
    failures: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[int] = mapped_column(Integer, default=0)
    last_count: Mapped[int] = mapped_column(Integer, default=0)
    cycle_started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class JobPosting(Base):
    __tablename__ = "job_postings"
    __table_args__ = (UniqueConstraint("owner_id", "canonical_url"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    normalized_title: Mapped[str] = mapped_column(String(300), index=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    arrangement: Mapped[str | None] = mapped_column(String(30), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    canonical_url: Mapped[str] = mapped_column(String(2000))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_source_id: Mapped[str] = mapped_column(ForeignKey("job_sources.id"))
    discovered_at: Mapped[str] = mapped_column(String(40), default=now)
    last_seen_at: Mapped[str] = mapped_column(String(40), default=now)
    posted_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1)


class JobPostingVersion(Base):
    __tablename__ = "job_posting_versions"
    __table_args__ = (UniqueConstraint("job_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("job_sources.id"))
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class JobSourceRecord(Base):
    __tablename__ = "job_source_records"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_id: Mapped[str] = mapped_column(ForeignKey("job_sources.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[str] = mapped_column(String(40), default=now)
    posted_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_seen_at: Mapped[str] = mapped_column(String(40), default=now)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    normalized_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    # Raw provider payloads are deliberately never retained in Phase 2.


class SearchTitle(Base):
    __tablename__ = "search_titles"
    __table_args__ = (UniqueConstraint("owner_id", "title"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    role_family_id: Mapped[str | None] = mapped_column(ForeignKey("role_families.id"), nullable=True)


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    source_ids: Mapped[list[str]] = mapped_column(JSON)


class SearchRun(Base):
    __tablename__ = "search_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    saved_search_id: Mapped[str | None] = mapped_column(ForeignKey("saved_searches.id"), nullable=True)
    started_at: Mapped[str] = mapped_column(String(40), default=now)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    state: Mapped[str] = mapped_column(String(30), default="running")
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

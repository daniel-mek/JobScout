from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import now, uid


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("owner_id", "job_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    applied_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resume_version_id: Mapped[str | None] = mapped_column(ForeignKey("resume_versions.id"), nullable=True)
    next_action: Mapped[str] = mapped_column(String(500), default="")
    next_action_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    follow_up_days: Mapped[int] = mapped_column(Integer, default=14)


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    source: Mapped[str] = mapped_column(String(30), default="USER")
    note: Mapped[str] = mapped_column(Text, default="")


class ApplicationSnapshot(Base):
    __tablename__ = "application_snapshots"
    __table_args__ = (UniqueConstraint("application_id", "stage"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("job_sources.id"), index=True)
    stage: Mapped[str] = mapped_column(String(30))
    job_revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    match: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    restriction: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(Text)
    due_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

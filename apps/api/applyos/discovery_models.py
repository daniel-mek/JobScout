from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import now, uid


class JobReview(Base):
    __tablename__ = "job_reviews"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), primary_key=True)
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    saved_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    job_revision: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(40), nullable=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    disabled_types: Mapped[list[str]] = mapped_column(JSON, default=list)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("owner_id", "event_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_key: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(60))
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class SavedDiscoverySearch(Base):
    __tablename__ = "saved_discovery_searches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    filters: Mapped[dict[str, Any]] = mapped_column(JSON)

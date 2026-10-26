"""Owner-scoped tracking. Only explicit user actions change application status."""

import csv
import io
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from .application_models import Application, ApplicationEvent, ApplicationSnapshot, ApplicationStatusHistory
from .application_schemas import ActionInput, CreateApplication, EventInput, Transition
from .jobs_models import JobPosting, JobSource, SourcePolicy
from .jobs_service import JobService, owner_lock, permitted
from .match_models import JobMatch
from .models import Resume, ResumeVersion, now

RESTRICTED = "Description and derived match archive unavailable under the current source storage policy."


class ApplicationService(JobService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshot_policies: dict[str, SourcePolicy] = {}

    def snapshot(self, row, stage):
        if self.db.scalar(
            select(ApplicationSnapshot.id).where(
                ApplicationSnapshot.application_id == row.id, ApplicationSnapshot.stage == stage
            )
        ):
            return
        job = self.owned(JobPosting, row.job_id)
        source = self.db.get(JobSource, job.content_source_id)
        assert source is not None
        policy = self.db.get(SourcePolicy, source.policy_id, with_for_update=True)
        assert policy is not None
        data = {**self.summary(job), **permitted(job.data, policy)}
        match = self.db.scalar(
            select(JobMatch)
            .where(
                JobMatch.owner_id == self.owner,
                JobMatch.job_id == job.id,
                JobMatch.job_revision == job.revision,
                *([JobMatch.resume_version_id == row.resume_version_id] if stage == "APPLIED" else []),
            )
            .order_by(JobMatch.calculated_at.desc(), JobMatch.id.desc())
            .limit(1)
        )
        self.db.add(
            ApplicationSnapshot(
                application_id=row.id,
                source_id=source.id,
                stage=stage,
                job_revision=job.revision,
                data=data,
                match=dict(
                    result=match.result,
                    calculated_at=match.calculated_at,
                    profile_revision=match.profile_revision,
                    resume_version_id=match.resume_version_id,
                    algorithm_version=match.algorithm_version,
                )
                if match and policy.description_storage == "allowed"
                else None,
                restriction=None if policy.description_storage == "allowed" else RESTRICTED,
            )
        )

    def create(self, data: CreateApplication):
        owner_lock(self.db, self.owner)
        self.owned(JobPosting, data.job_id)
        existing = self.db.scalar(
            select(Application).where(Application.owner_id == self.owner, Application.job_id == data.job_id)
        )
        if existing:
            # Reopen the existing timeline deliberately instead of duplicating it.
            return self.detail(existing.id)
        row = Application(owner_id=self.owner, job_id=data.job_id, status=data.status)
        self.db.add(row)
        self.db.flush()
        self.db.add(ApplicationStatusHistory(application_id=row.id, new_status=data.status))
        self.snapshot(row, data.status)
        self.db.commit()
        return self.detail(row.id)

    def checked(self, key, revision):
        owner_lock(self.db, self.owner)
        row = self.owned(Application, key)
        if row.revision != revision:
            raise HTTPException(409, "This application changed. Reload before saving.")
        return row

    def transition(self, key, data: Transition):
        row = self.checked(key, data.expected_revision)
        if row.status == data.status:
            return self.detail(row.id)
        if data.status == "APPLIED" and row.applied_at is None:
            if not data.confirm_applied:
                raise HTTPException(422, "Confirm that you submitted the application yourself.")
            resume = self.db.scalar(
                select(ResumeVersion)
                .join(Resume)
                .where(ResumeVersion.id == data.resume_version_id, Resume.owner_id == self.owner)
            )
            if resume is None or resume.confirmed_profile is None:
                raise HTTPException(422, "Select your confirmed resume version used to apply.")
            row.resume_version_id = resume.id
            row.applied_at = now()
            self.snapshot(row, "APPLIED")
        elif data.status not in {"SAVED", "PREPARING", "REJECTED", "WITHDRAWN"} and row.applied_at is None:
            raise HTTPException(422, "Mark as Applied before recording later application stages.")
        if data.status == "PREPARING":
            self.snapshot(row, "PREPARING")
        self.db.add(
            ApplicationStatusHistory(
                application_id=row.id,
                previous_status=row.status,
                new_status=data.status,
                note=data.note,
            )
        )
        row.status = data.status
        row.revision += 1
        row.updated_at = now()
        self.db.commit()
        return self.detail(row.id)

    def action(self, key, data: ActionInput):
        row = self.checked(key, data.expected_revision)
        row.next_action = data.next_action
        row.next_action_date = data.next_action_date.isoformat() if data.next_action_date else None
        row.follow_up_days = data.follow_up_days
        row.revision += 1
        row.updated_at = now()
        self.db.commit()
        return self.detail(row.id)

    def event(self, key, data: EventInput):
        owner_lock(self.db, self.owner)
        row = self.owned(Application, key)
        self.db.add(
            ApplicationEvent(
                application_id=row.id,
                kind=data.kind,
                text=data.text,
                due_date=data.due_date.isoformat() if data.due_date else None,
            )
        )
        row.updated_at = now()
        row.revision += 1
        self.db.commit()
        return self.detail(row.id)

    def complete(self, key, event_id, completed):
        owner_lock(self.db, self.owner)
        row = self.owned(Application, key)
        event = self.db.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == row.id, ApplicationEvent.id == event_id
            )
        )
        if event is None:
            raise HTTPException(404, "Event not found.")
        if bool(event.completed_at) != completed:
            event.completed_at = now() if completed else None
            row.updated_at = now()
            row.revision += 1
        self.db.commit()
        return self.detail(row.id)

    def snapshot_view(self, snapshot):
        policy = self.snapshot_policies.get(snapshot.source_id)
        if policy is None:
            source = self.db.get(JobSource, snapshot.source_id)
            assert source is not None
            policy = self.db.get(SourcePolicy, source.policy_id)
            assert policy is not None
            self.snapshot_policies[snapshot.source_id] = policy
        allowed = policy.description_storage == "allowed"
        return dict(
            stage=snapshot.stage,
            job_revision=snapshot.job_revision,
            created_at=snapshot.created_at,
            data=permitted(snapshot.data, policy),
            match=snapshot.match if allowed else None,
            restriction=snapshot.restriction if allowed else RESTRICTED,
        )

    def view(self, row, snapshots, events, clock):
        chosen = next(
            (s for s in snapshots if s.stage == "APPLIED"),
            next((s for s in snapshots if s.stage == "PREPARING"), snapshots[0]),
        )
        snap = self.snapshot_view(chosen)
        pending = sorted((e for e in events if e.due_date and not e.completed_at), key=lambda e: e.due_date)
        dates = [e.due_date for e in pending]
        if row.next_action_date:
            dates.append(row.next_action_date)
        follow_up = row.status == "APPLIED" and clock >= (
            datetime.fromisoformat(row.updated_at) + timedelta(days=row.follow_up_days)
        )
        return dict(
            id=row.id,
            job_id=row.job_id,
            status=row.status,
            revision=row.revision,
            created_at=row.created_at,
            updated_at=row.updated_at,
            applied_at=row.applied_at,
            resume_version_id=row.resume_version_id,
            next_action=row.next_action,
            next_action_date=row.next_action_date,
            follow_up_days=row.follow_up_days,
            due_date=min(dates) if dates else None,
            follow_up_suggestion="Consider following up" if follow_up else None,
            title=snap["data"]["title"],
            company=snap["data"]["company"],
            application_url=snap["data"]["application_url"],
            match=snap["match"],
            sources=snap["data"].get("sources", []),
        )

    def listing(self, offset=0, limit=50, status=None, company="", role=""):
        # Snapshot metadata keeps the original role/company after posting changes.
        query = select(Application).where(Application.owner_id == self.owner)
        initial = select(ApplicationSnapshot.application_id).where(
            ApplicationSnapshot.data["company"].as_string().icontains(company, autoescape=True),
            ApplicationSnapshot.data["title"].as_string().icontains(role, autoescape=True),
        )
        query = query.where(Application.id.in_(initial))
        if status:
            query = query.where(Application.status == status)
        total = self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = list(
            self.db.scalars(
                query.order_by(Application.updated_at.desc(), Application.id).offset(offset).limit(limit)
            )
        )
        ids = [r.id for r in rows]
        snapshots = list(
            self.db.scalars(
                select(ApplicationSnapshot)
                .where(ApplicationSnapshot.application_id.in_(ids))
                .order_by(ApplicationSnapshot.created_at, ApplicationSnapshot.id)
            )
        )
        events = list(
            self.db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id.in_(ids)))
        )
        clock = datetime.fromisoformat(now())
        grouped_snapshots: dict[str, list[ApplicationSnapshot]] = {}
        grouped_events: dict[str, list[ApplicationEvent]] = {}
        for snapshot in snapshots:
            grouped_snapshots.setdefault(snapshot.application_id, []).append(snapshot)
        for event in events:
            grouped_events.setdefault(event.application_id, []).append(event)
        return dict(
            total=total,
            offset=offset,
            limit=limit,
            as_of=clock.isoformat(),
            items=[
                self.view(
                    r,
                    grouped_snapshots[r.id],
                    grouped_events.get(r.id, []),
                    clock,
                )
                for r in rows
            ],
        )

    def detail(self, key):
        row = self.owned(Application, key)
        snapshots = list(
            self.db.scalars(
                select(ApplicationSnapshot)
                .where(ApplicationSnapshot.application_id == key)
                .order_by(ApplicationSnapshot.created_at, ApplicationSnapshot.id)
            )
        )
        events = list(
            self.db.scalars(
                select(ApplicationEvent)
                .where(ApplicationEvent.application_id == key)
                .order_by(ApplicationEvent.created_at, ApplicationEvent.id)
            )
        )
        history = list(
            self.db.scalars(
                select(ApplicationStatusHistory)
                .where(ApplicationStatusHistory.application_id == key)
                .order_by(ApplicationStatusHistory.created_at, ApplicationStatusHistory.id)
            )
        )
        resume = self.db.get(ResumeVersion, row.resume_version_id) if row.resume_version_id else None
        return {
            **self.view(row, snapshots, events, datetime.fromisoformat(now())),
            "snapshots": [self.snapshot_view(s) for s in snapshots],
            "resume": dict(id=resume.id, version=resume.version, filename=resume.filename)
            if resume
            else None,
            "history": [
                dict(
                    previous_status=h.previous_status,
                    new_status=h.new_status,
                    created_at=h.created_at,
                    source=h.source,
                    note=h.note,
                )
                for h in history
            ],
            "events": [
                dict(
                    id=e.id,
                    kind=e.kind,
                    text=e.text,
                    due_date=e.due_date,
                    completed_at=e.completed_at,
                    created_at=e.created_at,
                )
                for e in events
            ],
        }

    def export(self):
        data = self.listing(limit=10001)
        if data["total"] > 10000:
            raise HTTPException(422, "Export supports up to 10,000 applications at a time.")
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        fields = [
            "company",
            "title",
            "status",
            "applied_at",
            "next_action",
            "next_action_date",
            "due_date",
            "application_url",
            "resume_match",
            "application_priority",
            "resume_version",
            "notes",
            "source_attribution",
            "source_urls",
        ]
        writer.writerow(fields)
        resumes = {
            r.id: r.version
            for r in self.db.scalars(select(ResumeVersion).join(Resume).where(Resume.owner_id == self.owner))
        }
        notes: dict[str, list[str]] = {}
        for event in self.db.scalars(
            select(ApplicationEvent)
            .join(Application)
            .where(Application.owner_id == self.owner, ApplicationEvent.kind == "NOTE")
            .order_by(ApplicationEvent.created_at, ApplicationEvent.id)
        ):
            notes.setdefault(event.application_id, []).append(event.created_at + ": " + event.text)
        for row in data["items"]:
            row["resume_match"] = row["match"]["result"].get("resume_match") if row["match"] else None
            row["application_priority"] = (
                row["match"]["result"].get("application_priority") if row["match"] else None
            )
            row["resume_version"] = resumes.get(row["resume_version_id"])
            row["notes"] = "\n".join(notes.get(row["id"], []))
            row["source_attribution"] = "; ".join(s["attribution"] for s in row["sources"])
            row["source_urls"] = "; ".join(s["url"] for s in row["sources"])
            # Quoting alone does not stop spreadsheet formula interpretation.
            writer.writerow([csv_safe(row.get(field)) for field in fields])
        return output.getvalue()


def csv_safe(value):
    text = str(value) if value is not None else ""
    return (
        "'" + text
        if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@"))
        else text
    )

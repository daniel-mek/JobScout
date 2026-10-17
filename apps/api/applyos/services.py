import hashlib
import re
import uuid
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.orm import Session

from . import repositories as repo
from .config import Settings
from .models import (
    CandidateProfile,
    CandidateSkill,
    CareerPreference,
    Certification,
    Education,
    Experience,
    HardRequirement,
    JobSearchPreference,
    ProfileRevision,
    Project,
    Resume,
    ResumeVersion,
    RoleFamily,
    User,
    now,
)
from .parsing import DeterministicResumeParser, IsolatedTextExtractor, ResumeParser, ResumeTextExtractor
from .schemas import CareerSelection, Preferences, ProfileData, ProfileReview, Requirements
from .storage import FileStorage

ITEMS: dict[str, type[Education] | type[Experience] | type[Project] | type[Certification]] = {
    "education": Education,
    "experience": Experience,
    "projects": Project,
    "certifications": Certification,
}


def version_summary(row: ResumeVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "version": row.version,
        "filename": row.filename,
        "size_bytes": row.size_bytes,
        "mime_type": row.mime_type,
        "created_at": row.created_at,
        "parser": row.parser,
        "confirmed": row.confirmed_profile is not None,
    }


class ProfileService:
    def __init__(self, db: Session, owner: str):
        self.db, self.owner = db, owner

    def current(self) -> dict[str, Any]:
        profile = repo.profile_for(self.db, self.owner)
        if not profile or profile.revision == 0:
            return {"revision": 0, "profile": None}
        # A revision is the authoritative ordered snapshot; evidence indices must not drift on row ordering.
        revision = self.db.scalar(
            select(ProfileRevision).where(
                ProfileRevision.profile_id == profile.id, ProfileRevision.revision == profile.revision
            )
        )
        data = (
            revision.data
            if revision
            else ProfileData(
                name=profile.name,
                location=profile.location,
                graduation_date=profile.graduation_date,
                summary=profile.summary,
            ).model_dump()
        )
        return {
            "revision": profile.revision,
            "profile": data,
            "resume_version_id": profile.reviewed_resume_version_id,
        }

    def review(self, request: ProfileReview) -> dict[str, Any]:
        profile = repo.profile_for(self.db, self.owner, lock=True)
        version = repo.version_for(self.db, self.owner, request.resume_version_id)
        if not profile or not version:
            raise HTTPException(404, "Resume version not found.")
        latest = repo.versions_for(self.db, self.owner)[0]
        if version.id != latest.id:
            raise HTTPException(409, "A newer resume is waiting for review. Reload the page.")
        if profile.revision != request.expected_revision:
            raise HTTPException(409, "Your profile changed in another tab. Reload before saving.")
        data = request.profile.model_dump()
        result = self.db.execute(
            update(CandidateProfile)
            .where(CandidateProfile.id == profile.id, CandidateProfile.revision == request.expected_revision)
            .values(
                revision=request.expected_revision + 1,
                name=data["name"],
                location=data["location"],
                graduation_date=data["graduation_date"],
                summary=data["summary"],
                reviewed_resume_version_id=version.id,
                updated_at=now(),
            )
        )
        if cast(CursorResult[Any], result).rowcount != 1:
            raise HTTPException(409, "Profile changed. Reload before saving.")
        for field, model in ITEMS.items():
            self.db.execute(delete(model).where(model.profile_id == profile.id))
            for item in data[field]:
                self.db.add(model(profile_id=profile.id, **item))
        self.db.execute(delete(CandidateSkill).where(CandidateSkill.profile_id == profile.id))
        for item in data["skills"]:
            skill = repo.skill_for(self.db, item["name"])
            self.db.add(
                CandidateSkill(
                    profile_id=profile.id, skill_id=skill.id, **{k: v for k, v in item.items() if k != "name"}
                )
            )
        self.db.add(ProfileRevision(profile_id=profile.id, revision=request.expected_revision + 1, data=data))
        if version.confirmed_profile is None:
            version.confirmed_profile = data
        self.db.commit()
        self.db.expire_all()
        return self.current()


class ResumeService:
    def __init__(
        self,
        db: Session,
        owner: str,
        config: Settings,
        storage: FileStorage,
        extractor: ResumeTextExtractor | None = None,
        parser: ResumeParser | None = None,
    ):
        self.db, self.owner, self.config, self.storage = db, owner, config, storage
        self.extractor = extractor or IsolatedTextExtractor()
        self.parser = parser or DeterministicResumeParser()

    def upload(self, filename: str, mime: str, content: bytes) -> dict[str, Any]:
        name = filename.replace("\\", "/").split("/")[-1]
        extension = name.rsplit(".", 1)[-1].lower()
        allowed = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        if extension not in allowed or mime != allowed[extension]:
            raise HTTPException(415, "Choose a PDF or DOCX with its matching file type.")
        if not content or len(content) > self.config.max_upload_bytes:
            raise HTTPException(413, "The resume must be between 1 byte and 5 MB.")
        text = self.extractor.extract(content, extension)
        try:
            parsed = ProfileData.model_validate(self.parser.parse(text).model_dump(warnings="error"))
        except Exception:
            raise HTTPException(422, "Resume parsing failed validation. Please try another file.") from None
        resume = repo.resume_for(self.db, self.owner, lock=True)
        if not resume:
            raise HTTPException(409, "Your account is not initialized. Sign in again.")
        previous = repo.versions_for(self.db, self.owner)
        key = f"{uuid.uuid4().hex}.{extension}"
        version = ResumeVersion(
            resume_id=resume.id,
            version=(previous[0].version + 1 if previous else 1),
            filename=re.sub(r"[^\w.() -]", "_", name)[:200],
            mime_type=allowed[extension],
            storage_key=key,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            extracted_text=text,
            parsed_profile=parsed.model_dump(),
            parser=self.parser.name,
        )
        self.storage.put(key, content)
        try:
            self.db.add(version)
            user = self.db.get(User, self.owner)
            if user:
                user.onboarding_complete = False
            self.db.commit()
        except Exception:
            self.db.rollback()
            self.storage.delete(key)
            raise
        return {
            "resume": version_summary(version),
            "draft": parsed.model_dump(),
            "extracted_text": text,
            "notice": "Deterministic extraction groups literal text and may leave fields blank. Review every section; no AI service was called.",
        }

    def detail(self, version_id: str) -> dict[str, Any]:
        row = repo.version_for(self.db, self.owner, version_id)
        if not row:
            raise HTTPException(404, "Resume version not found.")
        return {
            "resume": version_summary(row),
            "draft": row.parsed_profile,
            "extracted_text": row.extracted_text,
            "confirmed_profile": row.confirmed_profile,
        }


class OnboardingService:
    def __init__(self, db: Session, owner: str):
        self.db, self.owner = db, owner

    def state(self) -> dict[str, Any]:
        versions = repo.versions_for(self.db, self.owner)
        profile = repo.profile_for(self.db, self.owner)
        role_ids = list(
            self.db.scalars(
                select(CareerPreference.role_family_id).where(CareerPreference.owner_id == self.owner)
            )
        )
        prefs = self.db.get(JobSearchPreference, self.owner)
        hard = self.db.get(HardRequirement, self.owner)
        step = (
            "upload"
            if not versions
            else "review"
            if versions[0].confirmed_profile is None
            else "paths"
            if not role_ids
            else "preferences"
            if prefs is None
            else "requirements"
            if hard is None
            else "complete"
        )
        return {
            "next_step": step,
            "complete": step == "complete",
            "latest_resume": version_summary(versions[0]) if versions else None,
            "profile_revision": profile.revision if profile else 0,
            "role_ids": role_ids,
            "preferences": prefs.data if prefs else None,
            "requirements": hard.data if hard else None,
        }

    def paths(self, data: CareerSelection) -> None:
        ids = set(data.role_ids)
        known = set(self.db.scalars(select(RoleFamily.id).where(RoleFamily.id.in_(ids))))
        if known != ids:
            raise HTTPException(422, "Select valid career paths.")
        self.db.execute(delete(CareerPreference).where(CareerPreference.owner_id == self.owner))
        self.db.add_all([CareerPreference(owner_id=self.owner, role_family_id=role) for role in sorted(ids)])
        self.db.commit()

    def preferences(self, data: Preferences) -> None:
        record = self.db.get(JobSearchPreference, self.owner)
        if record:
            record.data = data.model_dump()
        else:
            self.db.add(JobSearchPreference(owner_id=self.owner, data=data.model_dump()))
        self.db.commit()

    def requirements(self, data: Requirements) -> None:
        record = self.db.get(HardRequirement, self.owner)
        if record:
            record.data = data.model_dump()
        else:
            self.db.add(HardRequirement(owner_id=self.owner, data=data.model_dump()))
        self.db.commit()

    def finish(self) -> dict[str, Any]:
        state = self.state()
        if not state["complete"]:
            raise HTTPException(
                409, "Complete profile review, career paths, preferences, and hard requirements first."
            )
        user = self.db.get(User, self.owner)
        if user:
            user.onboarding_complete = True
        self.db.commit()
        return state


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def signup(self, email: str, password: str) -> User:
        from sqlalchemy.exc import IntegrityError

        from .security import hasher

        user = User(email=email.lower(), password_hash=hasher.hash(password))
        self.db.add(user)
        try:
            self.db.flush()
            self.db.add_all([Resume(owner_id=user.id), CandidateProfile(owner_id=user.id)])
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                400, "Unable to create this account. Try signing in or use another email."
            ) from None
        return user

    def login(self, email: str, password: str) -> User:
        from .security import DUMMY_HASH, hasher, verify_password

        user = self.db.scalar(select(User).where(User.email == email.lower()))
        valid = verify_password(user.password_hash if user else DUMMY_HASH, password)
        if not user or not valid:
            raise HTTPException(401, "Email or password is incorrect.")
        if hasher.check_needs_rehash(user.password_hash):
            user.password_hash = hasher.hash(password)
        return user

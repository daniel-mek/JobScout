from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CandidateProfile, Resume, ResumeVersion


def profile_for(db: Session, owner: str, *, lock: bool = False) -> CandidateProfile | None:
    query = select(CandidateProfile).where(CandidateProfile.owner_id == owner)
    return db.scalar(query.with_for_update() if lock else query)


def resume_for(db: Session, owner: str, *, lock: bool = False) -> Resume | None:
    query = select(Resume).where(Resume.owner_id == owner)
    return db.scalar(query.with_for_update() if lock else query)


def versions_for(db: Session, owner: str) -> list[ResumeVersion]:
    return list(
        db.scalars(
            select(ResumeVersion)
            .join(Resume)
            .where(Resume.owner_id == owner)
            .order_by(ResumeVersion.version.desc())
        )
    )


def version_for(db: Session, owner: str, version_id: str) -> ResumeVersion | None:
    return db.scalar(
        select(ResumeVersion).join(Resume).where(Resume.owner_id == owner, ResumeVersion.id == version_id)
    )


def skill_for(db: Session, name: str):
    """Race-safe shared vocabulary insertion; candidate evidence stays owner-scoped."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    from .models import Skill, uid

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        statement = (
            pg_insert(Skill)
            .values(id=uid(), name=name.casefold())
            .on_conflict_do_nothing(index_elements=["name"])
        )
    else:
        sqlite_statement = (
            sqlite_insert(Skill)
            .values(id=uid(), name=name.casefold())
            .on_conflict_do_nothing(index_elements=["name"])
        )
    db.execute(
        statement if db.bind is not None and db.bind.dialect.name == "postgresql" else sqlite_statement
    )
    return db.scalar(select(Skill).where(Skill.name == name.casefold()))

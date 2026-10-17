import hashlib
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from .config import Settings
from .models import AuthAttempt, Session, User

COOKIE = "applyos_session"
CSRF_COOKIE = "applyos_csrf"
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except VerificationError:
        return False


def throttle(db: DBSession, key: str, limit: int = 20) -> None:
    stamp = int(time.time())
    # Persistent per-key counter; advisory locking serializes competing requests on PostgreSQL.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(digest(key)[:15], 16)})
    record = db.get(AuthAttempt, digest(key))
    if record is None:
        record = AuthAttempt(key=digest(key), window_start=stamp, count=0)
        db.add(record)
    elif stamp - record.window_start >= 900:
        record.window_start, record.count = stamp, 0
    record.count += 1
    blocked = record.count > limit
    db.commit()
    if blocked:
        raise HTTPException(
            429, "Too many attempts. Please try again in 15 minutes.", headers={"Retry-After": "900"}
        )


def create_session(db: DBSession, user: User, config: Settings) -> tuple[str, str]:
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.add(
        Session(
            token_hash=digest(token),
            user_id=user.id,
            csrf_hash=digest(csrf),
            expires_at=int(time.time()) + config.session_days * 86400,
        )
    )
    db.flush()
    return token, csrf


def session_user(db: DBSession, token: str) -> tuple[Session, User]:
    record = db.get(Session, digest(token))
    if not record or record.expires_at <= int(time.time()):
        raise HTTPException(401, "Please sign in.")
    user = db.scalar(select(User).where(User.id == record.user_id))
    if not user:
        raise HTTPException(401, "Please sign in.")
    return record, user

import logging
import secrets
import uuid
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session as DBSession

from . import repositories as repo
from .config import Settings, settings
from .db import make_database
from .jobs_routes import router_for
from .models import ProfileRevision, RoleFamily, Session, User
from .schemas import CareerSelection, Credentials, Preferences, ProfileReview, Requirements
from .security import COOKIE, CSRF_COOKIE, create_session, digest, session_user, throttle
from .services import AuthService, OnboardingService, ProfileService, ResumeService, version_summary
from .storage import storage_for

logger = logging.getLogger("applyos")


def create_app(config: Settings | None = None) -> FastAPI:
    config = config or settings()
    engine, sessions = make_database(config)
    app = FastAPI(
        title="ApplyOS API",
        version="2.0.0",
        docs_url="/docs" if config.environment != "production" else None,
    )
    app.state.engine, app.state.sessions = engine, sessions
    app.state.config = config
    app.state.storage = storage_for(config)

    @app.middleware("http")
    async def request_controls(request: Request, call_next):
        request_id = str(uuid.uuid4())
        if (
            request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.headers.get("origin") != config.web_origin
        ):
            return JSONResponse({"detail": "Untrusted request origin."}, status_code=403)
        limit = config.max_upload_bytes + 65536
        length = request.headers.get("content-length", "")
        if length and (not length.isdigit() or int(length) > limit):
            return JSONResponse({"detail": "Request is too large."}, status_code=413)
        original_receive = request._receive
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await original_receive()
            received += len(message.get("body", b""))
            if received > limit:
                raise HTTPException(413, "Request is too large.")
            return message

        request._receive = bounded_receive
        try:
            result = await call_next(request)
        except Exception:
            logger.error("request_failed id=%s method=%s", request_id, request.method)
            result = JSONResponse(
                {"detail": "Something went wrong. Please try again.", "request_id": request_id},
                status_code=500,
            )
        result.headers.update(
            {
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Cache-Control": "no-store",
            }
        )
        logger.info("request id=%s method=%s status=%s", request_id, request.method, result.status_code)
        return result

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _error):
        # Pydantic's default input field would echo passwords or resume data.
        return JSONResponse(
            {"detail": "Some fields are invalid. Check required fields, lengths, and formats."},
            status_code=422,
        )

    @app.exception_handler(IntegrityError)
    async def conflict(_request, _error):
        return JSONResponse({"detail": "The record changed. Reload and try again."}, status_code=409)

    def database() -> Generator[DBSession, None, None]:
        with sessions() as db:
            yield db

    DB = Annotated[DBSession, Depends(database)]

    def current_user(request: Request, db: DB) -> User:
        record, user = session_user(db, request.cookies.get(COOKIE, ""))
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            csrf = request.headers.get("x-csrf-token", "")
            if not csrf or not secrets.compare_digest(record.csrf_hash, digest(csrf)):
                raise HTTPException(403, "Your session could not be verified. Reload and try again.")
        return user

    Current = Annotated[User, Depends(current_user)]

    def set_cookies(response: Response, token: str, csrf: str) -> None:
        for name, value, http_only in ((COOKIE, token, True), (CSRF_COOKIE, csrf, False)):
            response.set_cookie(
                name,
                value,
                httponly=http_only,
                secure=config.cookie_secure,
                samesite="lax",
                max_age=config.session_days * 86400,
                path="/",
            )

    @app.get("/health")
    def health(db: DB):
        try:
            db.execute(text("SELECT id FROM users LIMIT 1"))
            db.execute(text("SELECT id FROM source_policies LIMIT 1"))
            return {"status": "healthy", "database": "ready"}
        except SQLAlchemyError:
            raise HTTPException(503, "Database is not ready. Run migrations.") from None

    def authenticate(data: Credentials, request: Request, response: Response, db: DBSession, signup: bool):
        address = request.client.host if request.client else "unknown"
        throttle(db, "ip:" + address)
        throttle(db, "email:" + str(data.email).lower(), limit=10)
        service = AuthService(db)
        user = (
            service.signup(str(data.email), data.password)
            if signup
            else service.login(str(data.email), data.password)
        )
        old = db.get(Session, digest(request.cookies.get(COOKIE, "")))
        if old:
            db.delete(old)
        token, csrf = create_session(db, user, config)
        db.commit()
        set_cookies(response, token, csrf)
        return {"id": user.id, "email": user.email}

    @app.post("/auth/signup", status_code=201)
    def signup(data: Credentials, request: Request, response: Response, db: DB):
        return authenticate(data, request, response, db, True)

    @app.post("/auth/login")
    def login(data: Credentials, request: Request, response: Response, db: DB):
        return authenticate(data, request, response, db, False)

    @app.get("/auth/me")
    def me(user: Current):
        return {"id": user.id, "email": user.email}

    @app.post("/auth/logout")
    def logout(request: Request, response: Response, db: DB, user: Current):
        record = db.get(Session, digest(request.cookies.get(COOKIE, "")))
        if record:
            db.delete(record)
            db.commit()
        response.delete_cookie(COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        return {"ok": True}

    @app.get("/onboarding")
    def onboarding(db: DB, user: Current):
        return OnboardingService(db, user.id).state()

    @app.post("/onboarding/complete")
    def complete(db: DB, user: Current):
        return OnboardingService(db, user.id).finish()

    @app.get("/role-families")
    def roles(db: DB, user: Current):
        return [
            {"id": row.id, "name": row.name}
            for row in db.scalars(select(RoleFamily).order_by(RoleFamily.name))
        ]

    @app.put("/career-preferences")
    def paths(data: CareerSelection, db: DB, user: Current):
        service = OnboardingService(db, user.id)
        service.paths(data)
        return service.state()

    @app.put("/preferences")
    def preferences(data: Preferences, db: DB, user: Current):
        service = OnboardingService(db, user.id)
        service.preferences(data)
        return service.state()

    @app.put("/requirements")
    def requirements(data: Requirements, db: DB, user: Current):
        service = OnboardingService(db, user.id)
        service.requirements(data)
        return service.state()

    @app.get("/profile")
    def profile(db: DB, user: Current):
        return ProfileService(db, user.id).current()

    @app.put("/profile")
    def review(data: ProfileReview, db: DB, user: Current):
        return ProfileService(db, user.id).review(data)

    @app.get("/profile/history")
    def history(db: DB, user: Current):
        profile = repo.profile_for(db, user.id)
        return (
            [
                {"revision": row.revision, "created_at": row.created_at, "profile": row.data}
                for row in db.scalars(
                    select(ProfileRevision)
                    .where(ProfileRevision.profile_id == profile.id)
                    .order_by(ProfileRevision.revision.desc())
                    .limit(100)
                )
            ]
            if profile
            else []
        )

    @app.get("/resumes")
    def resumes(db: DB, user: Current):
        return [version_summary(row) for row in repo.versions_for(db, user.id)]

    @app.post("/resumes", status_code=201)
    def upload(db: DB, user: Current, file: UploadFile = File(...)):
        throttle(db, "upload:" + user.id)
        content = file.file.read(config.max_upload_bytes + 1)
        file.file.close()
        return ResumeService(db, user.id, config, app.state.storage).upload(
            file.filename or "", file.content_type or "", content
        )

    @app.get("/resumes/{version_id}")
    def resume(version_id: str, db: DB, user: Current):
        return ResumeService(db, user.id, config, app.state.storage).detail(version_id)

    @app.get("/resumes/{version_id}/download")
    def download(version_id: str, db: DB, user: Current):
        row = repo.version_for(db, user.id, version_id)
        if not row:
            raise HTTPException(404, "Resume version not found.")
        return Response(
            app.state.storage.read(row.storage_key),
            media_type=row.mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="resume-v{row.version}.{row.storage_key.rsplit(".", 1)[-1]}"'
            },
        )

    @app.get("/dashboard")
    def dashboard(db: DB, user: Current):
        state = OnboardingService(db, user.id).state()
        if not state["complete"]:
            raise HTTPException(409, "Complete onboarding before opening the dashboard.")
        return {
            "account": {"email": user.email},
            "onboarding": state,
            "profile": ProfileService(db, user.id).current(),
            "resume_versions": len(repo.versions_for(db, user.id)),
            "notice": "Your foundation is ready. Personalized job discovery will connect in a later phase.",
        }

    app.include_router(router_for(database, current_user, config))
    return app


app = create_app()

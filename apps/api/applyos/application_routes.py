from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from .application_schemas import ActionInput, CreateApplication, EventInput, Status, Transition
from .applications import ApplicationService
from .models import User


def router_for(database, current_user):
    router = APIRouter()
    DB = Annotated[Session, Depends(database)]
    Current = Annotated[User, Depends(current_user)]

    @router.get("/applications")
    def applications(
        db: DB,
        user: Current,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        status: Status | None = None,
        company: str = Query("", max_length=200),
        role: str = Query("", max_length=300),
    ):
        return ApplicationService(db, user.id).listing(offset, limit, status, company, role)

    @router.post("/applications", status_code=201)
    def create(data: CreateApplication, db: DB, user: Current):
        return ApplicationService(db, user.id).create(data)

    @router.get("/applications/export.csv")
    def export(db: DB, user: Current):
        return Response(
            ApplicationService(db, user.id).export(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="applications.csv"',
                "Cache-Control": "no-store",
            },
        )

    @router.get("/applications/{key}")
    def detail(key: str, db: DB, user: Current):
        return ApplicationService(db, user.id).detail(key)

    @router.post("/applications/{key}/status")
    def transition(key: str, data: Transition, db: DB, user: Current):
        return ApplicationService(db, user.id).transition(key, data)

    @router.put("/applications/{key}/action")
    def action(key: str, data: ActionInput, db: DB, user: Current):
        return ApplicationService(db, user.id).action(key, data)

    @router.post("/applications/{key}/events", status_code=201)
    def event(key: str, data: EventInput, db: DB, user: Current):
        return ApplicationService(db, user.id).event(key, data)

    @router.patch("/applications/{key}/events/{event_id}")
    def complete(key: str, event_id: str, db: DB, user: Current, completed: bool = True):
        return ApplicationService(db, user.id).complete(key, event_id, completed)

    return router

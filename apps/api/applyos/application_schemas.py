from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal[
    "SAVED",
    "PREPARING",
    "APPLIED",
    "ONLINE_ASSESSMENT",
    "RECRUITER_SCREEN",
    "INTERVIEW",
    "FINAL_INTERVIEW",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateApplication(Input):
    job_id: str = Field(max_length=36)
    status: Literal["SAVED", "PREPARING"] = "PREPARING"


class Transition(Input):
    expected_revision: int = Field(ge=1)
    status: Status
    note: str = Field(default="", max_length=6000)
    resume_version_id: str | None = Field(default=None, max_length=36)
    confirm_applied: bool = False


class ActionInput(Input):
    expected_revision: int = Field(ge=1)
    next_action: str = Field(max_length=500)
    next_action_date: date | None = None
    follow_up_days: int = Field(default=14, ge=1, le=90)


class EventInput(Input):
    kind: Literal["NOTE", "ASSESSMENT", "INTERVIEW", "APPLICATION_DEADLINE", "FOLLOW_UP", "OTHER"]
    text: str = Field(min_length=1, max_length=6000)
    due_date: date | None = None

    @model_validator(mode="after")
    def deadline(self):
        if self.kind != "NOTE" and self.due_date is None:
            raise ValueError("Choose a due date for this event.")
        return self

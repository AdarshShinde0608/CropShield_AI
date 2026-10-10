from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ActionStatus = Literal["pending", "done", "needs_expert"]


class ActionCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"status": "pending", "note": "Check the field boundary."}
        },
    )

    status: ActionStatus
    note: str | None = Field(default=None, max_length=500)


class ActionUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"status": "done", "note": "Field inspected."}
        },
    )

    status: ActionStatus | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_update_value(self) -> "ActionUpdate":
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        if self.status is None and self.note is None:
            raise ValueError("At least one action field must be provided")
        return self


class ActionOut(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "id": "action-01",
                "user_id": "user-01",
                "field_id": "F012",
                "status": "pending",
                "note": "Check the field boundary.",
                "created_at": "2026-02-08T11:00:00Z",
                "updated_at": "2026-02-08T11:00:00Z",
            }
        },
    )

    id: str
    user_id: str
    field_id: str
    status: ActionStatus
    note: str | None = None
    created_at: datetime
    updated_at: datetime
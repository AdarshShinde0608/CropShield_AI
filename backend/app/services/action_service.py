from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.action import ActionCreate, ActionOut, ActionUpdate


class ActionNotFoundError(Exception):
    """Raised when the requested field or action does not exist."""


class ActionOwnershipError(Exception):
    """Raised when a user attempts to update another user's action."""


def _action_out(document: dict[str, Any]) -> ActionOut:
    return ActionOut(
        id=str(document["action_id"]),
        user_id=str(document["user_id"]),
        field_id=str(document["field_id"]),
        status=document["status"],
        note=document.get("note"),
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


async def list_field_actions(
    database: AsyncIOMotorDatabase,
    field_id: str,
    user_id: str,
) -> list[ActionOut]:
    field = await database.fields.find_one({"field_id": field_id}, {"_id": 0})
    if field is None:
        raise ActionNotFoundError

    documents = await database.actions.find(
        {"field_id": field_id, "user_id": user_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(length=None)
    return [_action_out(document) for document in documents]


async def create_field_action(
    database: AsyncIOMotorDatabase,
    field_id: str,
    user_id: str,
    request: ActionCreate,
) -> ActionOut:
    field = await database.fields.find_one({"field_id": field_id}, {"_id": 0})
    if field is None:
        raise ActionNotFoundError

    now = datetime.now(timezone.utc)
    document = {
        "action_id": uuid4().hex,
        "user_id": user_id,
        "field_id": field_id,
        **request.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    await database.actions.insert_one(document)
    return _action_out(document)


async def update_action(
    database: AsyncIOMotorDatabase,
    action_id: str,
    user_id: str,
    request: ActionUpdate,
) -> ActionOut:
    document = await database.actions.find_one(
        {"action_id": action_id},
        {"_id": 0},
    )
    if document is None:
        raise ActionNotFoundError
    if document.get("user_id") != user_id:
        raise ActionOwnershipError

    updates = request.model_dump(exclude_unset=True)
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await database.actions.update_one(
        {"action_id": action_id, "user_id": user_id},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise ActionOwnershipError

    updated_document = await database.actions.find_one(
        {"action_id": action_id, "user_id": user_id},
        {"_id": 0},
    )
    if updated_document is None:
        raise ActionNotFoundError
    return _action_out(updated_document)
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.schemas.action import ActionCreate, ActionOut, ActionUpdate
from app.services.action_service import (
    ActionNotFoundError,
    ActionOwnershipError,
    create_field_action,
    list_field_actions,
    update_action,
)

router = APIRouter(tags=["actions"])
DatabaseDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"detail": "Field or action was not found", "code": "NOT_FOUND"},
    )


@router.get(
    "/fields/{field_id}/actions",
    response_model=list[ActionOut],
    summary="List the current user's field actions",
)
async def get_actions(
    field_id: str,
    current_user: CurrentUser,
    database: DatabaseDep,
) -> list[ActionOut]:
    try:
        return await list_field_actions(database, field_id, current_user.id)
    except ActionNotFoundError as exc:
        raise _not_found() from exc


@router.post(
    "/fields/{field_id}/actions",
    response_model=ActionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record an inspection action",
)
async def post_action(
    field_id: str,
    request: ActionCreate,
    current_user: CurrentUser,
    database: DatabaseDep,
) -> ActionOut:
    try:
        return await create_field_action(database, field_id, current_user.id, request)
    except ActionNotFoundError as exc:
        raise _not_found() from exc


@router.patch(
    "/actions/{action_id}",
    response_model=ActionOut,
    summary="Update an owned inspection action",
)
async def patch_action(
    action_id: str,
    request: ActionUpdate,
    current_user: CurrentUser,
    database: DatabaseDep,
) -> ActionOut:
    try:
        return await update_action(database, action_id, current_user.id, request)
    except ActionNotFoundError as exc:
        raise _not_found() from exc
    except ActionOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "You do not own this action", "code": "FORBIDDEN"},
        ) from exc
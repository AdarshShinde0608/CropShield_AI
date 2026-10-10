from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.schemas.result import FieldResult
from app.schemas.timeseries import TimeseriesResponse
from app.services.field_service import (
    FieldNotFoundError,
    get_field_result,
    get_field_timeseries,
)

router = APIRouter(prefix="/fields", tags=["fields"])
DatabaseDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"detail": "Field was not found", "code": "NOT_FOUND"},
    )


@router.get("/{field_id}", response_model=FieldResult, summary="Get field result")
async def get_field(
    field_id: str,
    current_user: CurrentUser,
    database: DatabaseDep,
) -> FieldResult:
    del current_user
    try:
        return await get_field_result(database, field_id)
    except FieldNotFoundError as exc:
        raise _not_found() from exc


@router.get(
    "/{field_id}/timeseries",
    response_model=TimeseriesResponse,
    summary="Get field time series",
)
async def get_timeseries(
    field_id: str,
    current_user: CurrentUser,
    database: DatabaseDep,
) -> TimeseriesResponse:
    del current_user
    try:
        return await get_field_timeseries(database, field_id)
    except FieldNotFoundError as exc:
        raise _not_found() from exc
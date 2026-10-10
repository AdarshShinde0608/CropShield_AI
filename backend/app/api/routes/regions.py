from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.schemas.field import FieldCollection
from app.schemas.region import QueueItem, RegionOut, RegionSummary
from app.schemas.result import Risk
from app.services.region_service import (
    get_region_fields,
    get_region_queue,
    get_region_summary,
    list_regions,
)
from app.utils.geojson import feature_collection

router = APIRouter(prefix="/regions", tags=["regions"])
DatabaseDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]


def _not_found(resource: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"detail": f"{resource} was not found", "code": "NOT_FOUND"},
    )


@router.get("", response_model=list[RegionOut], summary="List regions")
async def get_regions(
    current_user: CurrentUser,
    database: DatabaseDep,
) -> list[RegionOut]:
    del current_user
    return await list_regions(database)


@router.get(
    "/{region_id}/summary",
    response_model=RegionSummary,
    summary="Get region summary",
)
async def get_summary(
    region_id: str,
    current_user: CurrentUser,
    database: DatabaseDep,
) -> RegionSummary:
    del current_user
    summary = await get_region_summary(database, region_id)
    if summary is None:
        raise _not_found("Region")
    return summary


@router.get(
    "/{region_id}/fields",
    response_model=FieldCollection,
    summary="Get region fields as GeoJSON",
)
async def get_fields(
    region_id: str,
    current_user: CurrentUser,
    database: DatabaseDep,
) -> FieldCollection:
    del current_user
    features = await get_region_fields(database, region_id)
    if features is None:
        raise _not_found("Region")
    return FieldCollection.model_validate(feature_collection(features))


@router.get(
    "/{region_id}/queue",
    response_model=list[QueueItem],
    summary="Get ranked inspection queue",
)
async def get_queue(
    region_id: str,
    current_user: CurrentUser,
    database: DatabaseDep,
    risk: Risk | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[QueueItem]:
    del current_user
    queue = await get_region_queue(database, region_id, risk, limit)
    if queue is None:
        raise _not_found("Region")
    return queue
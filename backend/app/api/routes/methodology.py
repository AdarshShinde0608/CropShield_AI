from typing import Annotated

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.schemas.region import MethodologyOut
from app.services.region_service import get_methodology

router = APIRouter(prefix="/methodology", tags=["methodology"])
DatabaseDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]


@router.get(
    "",
    response_model=MethodologyOut,
    summary="Describe the current analysis methodology",
)
async def methodology(database: DatabaseDep) -> MethodologyOut:
    return await get_methodology(database)
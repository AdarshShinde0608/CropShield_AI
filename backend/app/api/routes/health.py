from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    tags=["health"],
    summary="Check API health",
    description="Reports that the API process is responding.",
)
async def read_health() -> dict[str, str]:
    return {"status": "ok"}
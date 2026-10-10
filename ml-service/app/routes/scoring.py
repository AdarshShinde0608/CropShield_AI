from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.logging import get_logger
from app.core.model import ModelRuntime
from app.core.security import require_service_key
from app.schemas.scoring import (
    ScoreBatchRequest,
    ScoreBatchResponse,
    ScoreRequest,
    ScoreResponse,
)
from app.services.model_store import ModelStore
from app.services.scorer import score_field

logger = get_logger(__name__)
router = APIRouter(
    prefix="/v1",
    dependencies=[Depends(require_service_key)],
)


@router.get("/model-info", response_model=None)
async def model_info(request: Request) -> dict[str, object]:
    database = request.app.state.metadata_client[request.app.state.settings.mongodb_db]
    try:
        record = await database.model_artifacts.find_one(
            {"status": "active"},
            {
                "_id": 0,
                "model_version": 1,
                "name": 1,
                "task": 1,
                "class_mapping": 1,
                "input_specification": 1,
                "output_specification": 1,
                "artifact_checksums": 1,
                "framework_versions": 1,
                "training_data": 1,
                "attribution": 1,
                "measured_metrics": 1,
                "limitations": 1,
                "status": 1,
            },
        )
    except Exception as error:
        logger.warning(
            "model_metadata_unavailable",
            extra={
                "event": "model_metadata_unavailable",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail={
                "detail": "Model metadata is unavailable",
                "code": "MODEL_METADATA_UNAVAILABLE",
            },
        ) from error
    if record is None:
        raise HTTPException(
            status_code=503,
            detail={
                "detail": "No active model metadata is available",
                "code": "MODEL_NOT_LOADED",
            },
        )
    store: ModelStore = request.app.state.model_store
    return {
        **record,
        "enabled": bool(
            store.ready and store.runtime.version == record.get("model_version")
        ),
    }


@router.post("/score", response_model=ScoreResponse)
async def score(request: Request, body: ScoreRequest) -> ScoreResponse:
    if len(body.observations) > request.app.state.settings.max_observations_per_field:
        raise HTTPException(
            status_code=413,
            detail={
                "detail": "Field exceeds the configured observation limit",
                "code": "PAYLOAD_TOO_LARGE",
            },
        )
    store: ModelStore = request.app.state.model_store
    return score_field(
        body,
        store.runtime,
        model_ready=store.ready,
        model_error_code=store.error_code,
    )


@router.post("/score/batch", response_model=ScoreBatchResponse)
async def score_batch(
    request: Request,
    body: ScoreBatchRequest,
) -> ScoreBatchResponse:
    settings = request.app.state.settings
    if len(body.items) > settings.max_batch_size:
        raise HTTPException(
            status_code=413,
            detail={
                "detail": "Batch exceeds the configured item limit",
                "code": "PAYLOAD_TOO_LARGE",
            },
        )
    if any(
        len(item.observations) > settings.max_observations_per_field
        for item in body.items
    ):
        raise HTTPException(
            status_code=413,
            detail={
                "detail": "A field exceeds the configured observation limit",
                "code": "PAYLOAD_TOO_LARGE",
            },
        )
    store: ModelStore = request.app.state.model_store
    runtime: ModelRuntime = store.runtime
    results = [
        score_field(
            item,
            runtime,
            model_ready=store.ready,
            model_error_code=store.error_code,
        )
        for item in body.items
    ]
    return ScoreBatchResponse(items=results)

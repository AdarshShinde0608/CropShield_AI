from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date, datetime
from typing import Annotated, Any, Protocol

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.core.rate_limit import LoginRateLimiter
from app.schemas.ml import ScorePreviewOptions
from app.services.ml_client import MLServiceError
from app.services.region_service import get_current_season

router = APIRouter(tags=["ml"])
DatabaseDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]
logger = logging.getLogger(__name__)
_RISK_VALUES = ("normal", "watch", "alert", "cannot_assess")
_SERVICE_BATCH_SIZE = 32


class MLClientProtocol(Protocol):
    async def health(self, request_id: str | None = None) -> dict[str, Any]: ...

    async def ready(self, request_id: str | None = None) -> dict[str, Any]: ...

    async def model_info(self, request_id: str | None = None) -> dict[str, Any]: ...

    async def score(
        self,
        payload: Mapping[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]: ...

    async def score_batch(
        self,
        payload: Mapping[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]: ...


def _client(request: Request) -> MLClientProtocol:
    client = getattr(request.app.state, "ml_service_client", None)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail={
                "detail": "ML service client is unavailable",
                "code": "ML_UNAVAILABLE",
            },
        )
    return client


def _upstream_error(error: MLServiceError) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"detail": error.message, "code": error.code},
    )


def _request_id(request: Request) -> str | None:
    return request.headers.get("X-Request-ID")


def _threshold_supported(model_info: Mapping[str, Any]) -> bool:
    candidates: list[object] = [
        model_info.get("decision_threshold"),
        model_info.get("risk_mapping"),
    ]
    output_specification = model_info.get("output_specification")
    if isinstance(output_specification, Mapping):
        candidates.extend(
            [
                output_specification.get("decision_threshold"),
                output_specification.get("risk_mapping"),
            ]
        )
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        threshold = candidate.get("decision_threshold", candidate)
        if (
            isinstance(threshold, Mapping)
            and {"minimum", "maximum", "default"} <= threshold.keys()
        ):
            return True
    return False


def _preview_payload(
    field_id: str,
    season: Mapping[str, Any],
    observations: list[dict[str, Any]],
    decision_threshold: float | None,
) -> dict[str, Any]:
    season_id = season.get("season_id")
    season_label = season.get("label") or season_id
    if not isinstance(season_id, str) or not isinstance(season_label, str):
        raise HTTPException(
            status_code=503,
            detail={
                "detail": "Current season metadata is incomplete",
                "code": "ML_INPUT_UNAVAILABLE",
            },
        )

    service_observations: list[dict[str, Any]] = []
    baseline_observations: list[dict[str, Any]] = []
    for row in observations:
        if row.get("ndvi") is None:
            continue
        observation_date = row.get("date")
        if isinstance(observation_date, datetime):
            observation_date = observation_date.date().isoformat()
        elif isinstance(observation_date, date):
            observation_date = observation_date.isoformat()
        indices = row.get("indices")
        bands = row.get("bands")
        if not isinstance(indices, Mapping) or not isinstance(bands, Mapping):
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": (
                        "Stored observations lack the spectral indices and bands "
                        "required by the ML service"
                    ),
                    "code": "ML_INPUT_UNAVAILABLE",
                },
            )
        required_indices = {"NDVI", "NDWI", "EVI", "GNDVI", "SAVI"}
        required_bands = {"Red", "Green", "Blue", "NIR", "SWIR"}
        if not required_indices <= indices.keys() or not required_bands <= bands.keys():
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": (
                        "Stored observations lack the spectral indices and bands "
                        "required by the ML service"
                    ),
                    "code": "ML_INPUT_UNAVAILABLE",
                },
            )
        if not isinstance(observation_date, str) or not isinstance(row.get("dos"), int):
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "Stored observation dates and day-of-season are required",
                    "code": "ML_INPUT_UNAVAILABLE",
                },
            )
        if row.get("valid_frac") is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "Stored observation valid_frac is required",
                    "code": "ML_INPUT_UNAVAILABLE",
                },
            )
        service_observation: dict[str, Any] = {
            "date": observation_date,
            "dos": row.get("dos"),
            "ndvi": row.get("ndvi"),
            "valid_frac": row.get("valid_frac"),
            "season": season_label,
            "low_quality": bool(row.get("low_quality", False)),
            "is_interpolated": bool(row.get("is_interpolated", False)),
            "indices": {name: indices[name] for name in required_indices},
            "bands": {name: bands[name] for name in required_bands},
        }
        for optional_name in ("baseline_median", "baseline_sigma", "rain_z"):
            if row.get(optional_name) is not None:
                service_observation[optional_name] = row[optional_name]
        service_observations.append(service_observation)
        if row.get("baseline_median") is not None:
            baseline: dict[str, Any] = {
                "dos": row.get("dos"),
                "baseline_median": row["baseline_median"],
            }
            if row.get("baseline_sigma") is not None:
                baseline["baseline_sigma"] = row["baseline_sigma"]
            baseline_observations.append(baseline)

    if not service_observations:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "No current-season observations can be scored",
                "code": "ML_INPUT_UNAVAILABLE",
            },
        )
    payload: dict[str, Any] = {
        "field_id": field_id,
        "observations": service_observations,
        "baseline_observations": baseline_observations,
    }
    if decision_threshold is not None:
        payload["decision_threshold"] = decision_threshold
    return payload


async def _load_current_observations(
    database: AsyncIOMotorDatabase,
    field_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    field = await database.fields.find_one(
        {"field_id": field_id},
        {"_id": 0, "field_id": 1, "region_id": 1},
    )
    if field is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Field was not found", "code": "NOT_FOUND"},
        )
    season = await get_current_season(database)
    if season is None or not isinstance(season.get("season_id"), str):
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "No current season is configured",
                "code": "ML_INPUT_UNAVAILABLE",
            },
        )
    rows = await database.observations.find(
        {"field_id": field_id, "season_id": season["season_id"]},
        {"_id": 0},
    ).to_list(length=None)
    return season, rows


def _field_ids_in_region(database: AsyncIOMotorDatabase, region_id: str) -> Any:
    return database.fields.find(
        {"region_id": region_id},
        {"_id": 0, "field_id": 1},
    )


async def _warm_up(client: MLClientProtocol, request_id: str | None) -> None:
    try:
        await client.health(request_id=request_id)
    except MLServiceError as error:
        logger.info(
            "ml_warmup_attempt_failed",
            extra={"event": "ml_warmup_attempt_failed", "code": error.code},
        )


@router.get("/ml/status", summary="Check optional ML service readiness")
async def ml_status(
    request: Request,
    current_user: CurrentUser,
) -> dict[str, Any]:
    del current_user
    client = _client(request)
    try:
        return await client.ready(_request_id(request))
    except MLServiceError as error:
        raise _upstream_error(error) from error


@router.post(
    "/ml/warmup",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request ML service warmup",
)
async def ml_warmup(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
) -> dict[str, str]:
    del current_user
    if getattr(request.app.state, "ml_service_client", None) is None:
        return {"status": "disabled"}
    client_ip = request.client.host if request.client else "unknown"
    limiter: LoginRateLimiter = request.app.state.ml_warmup_rate_limiter
    if not limiter.allow(client_ip):
        raise HTTPException(
            status_code=429,
            detail={
                "detail": "ML warmup rate limit exceeded",
                "code": "RATE_LIMITED",
            },
        )
    background_tasks.add_task(_warm_up, _client(request), _request_id(request))
    return {"status": "accepted"}


@router.get("/model-info", summary="Get model metadata")
async def get_model_info(
    request: Request,
    current_user: CurrentUser,
    database: DatabaseDep,
) -> dict[str, Any]:
    del current_user
    client = getattr(request.app.state, "ml_service_client", None)
    if client is not None:
        try:
            info = await client.model_info(_request_id(request))
            return {**info, "source": "ml-service"}
        except MLServiceError as error:
            if error.code != "ML_WAKING":
                raise _upstream_error(error) from error
    fallback = await database.model_artifacts.find_one(
        {"status": "active"},
        {"_id": 0},
    )
    if fallback is None:
        unavailable_code = "ML_UNAVAILABLE" if client is None else "ML_WAKING"
        unavailable_message = (
            "ML service is disabled and no active model metadata is available"
            if client is None
            else "ML service is waking and no active model metadata is available"
        )
        raise HTTPException(
            status_code=503,
            detail={
                "detail": unavailable_message,
                "code": unavailable_code,
            },
        )
    return {
        **fallback,
        "source": "database",
        "enabled": False,
    }


@router.post(
    "/fields/{field_id}/score-preview",
    summary="Preview a field score without saving",
)
async def score_field_preview(
    field_id: str,
    request: Request,
    current_user: CurrentUser,
    database: DatabaseDep,
    options: ScorePreviewOptions | None = None,
) -> dict[str, Any]:
    del current_user
    season, observations = await _load_current_observations(database, field_id)
    threshold = options.decision_threshold if options else None
    client = _client(request)
    if threshold is not None:
        try:
            info = await client.model_info(_request_id(request))
        except MLServiceError as error:
            raise _upstream_error(error) from error
        if not _threshold_supported(info):
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "The active model does not allow threshold overrides",
                    "code": "VALIDATION_ERROR",
                },
            )
    payload = _preview_payload(field_id, season, observations, threshold)
    try:
        result = await client.score(payload, _request_id(request))
    except MLServiceError as error:
        raise _upstream_error(error) from error
    return {**result, "preview": True}


@router.post(
    "/regions/{region_id}/score-preview",
    summary="Preview region scores without saving",
)
async def score_region_preview(
    region_id: str,
    request: Request,
    current_user: CurrentUser,
    database: DatabaseDep,
    options: ScorePreviewOptions | None = None,
) -> dict[str, Any]:
    del current_user
    region = await database.regions.find_one(
        {"region_id": region_id},
        {"_id": 0, "region_id": 1},
    )
    if region is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Region was not found", "code": "NOT_FOUND"},
        )
    season = await get_current_season(database)
    if season is None or not isinstance(season.get("season_id"), str):
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "No current season is configured",
                "code": "ML_INPUT_UNAVAILABLE",
            },
        )
    fields = await _field_ids_in_region(database, region_id).to_list(length=None)
    client = _client(request)
    threshold = options.decision_threshold if options else None
    if threshold is not None:
        try:
            info = await client.model_info(_request_id(request))
        except MLServiceError as error:
            raise _upstream_error(error) from error
        if not _threshold_supported(info):
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "The active model does not allow threshold overrides",
                    "code": "VALIDATION_ERROR",
                },
            )

    count_by_risk = {risk: 0 for risk in _RISK_VALUES}
    for start in range(0, len(fields), _SERVICE_BATCH_SIZE):
        payloads: list[dict[str, Any]] = []
        for field in fields[start : start + _SERVICE_BATCH_SIZE]:
            field_id = field.get("field_id")
            if not isinstance(field_id, str) or not field_id:
                continue
            observations = await database.observations.find(
                {"field_id": field_id, "season_id": season["season_id"]},
                {"_id": 0},
            ).to_list(length=None)
            payloads.append(
                _preview_payload(field_id, season, observations, threshold)
            )
        if not payloads:
            continue
        try:
            response = await client.score_batch(
                {"items": payloads},
                _request_id(request),
            )
        except MLServiceError as error:
            raise _upstream_error(error) from error
        items = response.get("items")
        if not isinstance(items, list) or len(items) != len(payloads):
            raise HTTPException(
                status_code=503,
                detail={
                    "detail": "ML service returned an invalid batch response",
                    "code": "ML_UNAVAILABLE",
                },
            )
        for item in items:
            risk = item.get("risk") if isinstance(item, Mapping) else None
            if risk not in count_by_risk:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "detail": "ML service returned an invalid risk value",
                        "code": "ML_UNAVAILABLE",
                    },
                )
            count_by_risk[risk] += 1

    return {
        "region_id": region_id,
        "preview": True,
        "total_fields": len(fields),
        "scored_fields": sum(count_by_risk.values()),
        "counts_by_risk": count_by_risk,
    }

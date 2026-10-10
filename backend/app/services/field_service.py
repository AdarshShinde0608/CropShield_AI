from datetime import date, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.result import FieldResult
from app.schemas.timeseries import RainPoint, TimeseriesPoint, TimeseriesResponse
from app.services.region_service import get_current_season, get_latest_run


class FieldNotFoundError(Exception):
    """Raised when the requested field does not exist."""


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _parse_field_result(
    field_id: str,
    document: dict[str, Any] | None,
    is_synthetic: bool,
) -> FieldResult:
    if document is None:
        return FieldResult(
            field_id=field_id,
            risk="cannot_assess",
            confidence=0.0,
            confidence_label="low",
            n_valid_obs=0,
            baseline_years=0,
            is_synthetic=is_synthetic,
        )
    result = {**document, "field_id": field_id, "is_synthetic": is_synthetic}
    result.setdefault("risk", "cannot_assess")
    result.setdefault("confidence", 0.0)
    result.setdefault("confidence_label", "low")
    result.setdefault("n_valid_obs", 0)
    result.setdefault("baseline_years", 0)
    return FieldResult.model_validate(result)


async def _current_field_result(
    database: AsyncIOMotorDatabase,
    field_id: str,
) -> tuple[dict[str, Any] | None, bool]:
    season = await get_current_season(database)
    latest_run = await get_latest_run(database)
    if season is None or not season.get("season_id"):
        return None, bool(latest_run and latest_run.get("is_synthetic"))
    query: dict[str, Any] = {"field_id": field_id, "season_id": season["season_id"]}
    if latest_run and latest_run.get("run_id"):
        query["run_id"] = latest_run["run_id"]
    result = await database.field_results.find_one(query, {"_id": 0})
    is_synthetic = bool(
        result.get("is_synthetic", latest_run.get("is_synthetic", False))
        if result is not None and latest_run is not None
        else latest_run and latest_run.get("is_synthetic")
    )
    return result, is_synthetic


async def get_field_result(
    database: AsyncIOMotorDatabase,
    field_id: str,
) -> FieldResult:
    field = await database.fields.find_one({"field_id": field_id}, {"_id": 0})
    if field is None:
        raise FieldNotFoundError
    result, is_synthetic = await _current_field_result(database, field_id)
    if result is None and field.get("is_synthetic_boundary"):
        is_synthetic = True
    return _parse_field_result(field_id, result, is_synthetic)


async def get_field_timeseries(
    database: AsyncIOMotorDatabase,
    field_id: str,
) -> TimeseriesResponse:
    field = await database.fields.find_one(
        {"field_id": field_id},
        {"_id": 0, "field_id": 1, "region_id": 1},
    )
    if field is None:
        raise FieldNotFoundError

    season = await get_current_season(database)
    observations: list[dict[str, Any]] = []
    if season and season.get("season_id"):
        observations = await database.observations.find(
            {"field_id": field_id, "season_id": season["season_id"]},
            {"_id": 0},
        ).to_list(length=None)
    observations.sort(key=lambda row: _as_date(row.get("date")) or date.min)

    points: list[TimeseriesPoint] = []
    for observation in observations:
        baseline = observation.get("baseline_median")
        sigma = observation.get("baseline_sigma")
        numeric_baseline = isinstance(baseline, (int, float))
        numeric_sigma = isinstance(sigma, (int, float))
        band_low = baseline - sigma if numeric_baseline and numeric_sigma else None
        band_high = baseline + sigma if numeric_baseline and numeric_sigma else None
        parsed_date = _as_date(observation.get("date"))
        if parsed_date is None:
            continue
        points.append(
            TimeseriesPoint(
                date=parsed_date,
                ndvi=observation.get("ndvi"),
                baseline_median=baseline,
                band_low=band_low,
                band_high=band_high,
                z=observation.get("z"),
                low_quality=bool(observation.get("low_quality", False)),
                is_interpolated=bool(observation.get("is_interpolated", False)),
            )
        )

    result, _ = await _current_field_result(database, field_id)
    drop_start = _as_date(result.get("drop_start")) if result else None
    rainfall_documents: list[dict[str, Any]] = []
    region_id = field.get("region_id")
    if region_id is not None and points:
        rainfall_documents = await database.rainfall.find(
            {"region_id": region_id},
            {"_id": 0},
        ).to_list(length=None)

    first_date = points[0].date if points else None
    last_date = points[-1].date if points else None
    rainfall: list[RainPoint] = []
    for row in rainfall_documents:
        parsed_date = _as_date(row.get("date"))
        if parsed_date is None or first_date is None or last_date is None:
            continue
        if first_date <= parsed_date <= last_date:
            rainfall.append(
                RainPoint(
                    date=parsed_date,
                    rain_mm=row.get("rain_mm"),
                    rain14=row.get("rain14"),
                    rain30=row.get("rain30"),
                )
            )
    rainfall.sort(key=lambda row: row.date)
    return TimeseriesResponse(
        field_id=field_id,
        drop_start=drop_start,
        points=points,
        rainfall=rainfall,
    )
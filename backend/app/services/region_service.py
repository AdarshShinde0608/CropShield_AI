from datetime import date, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.region import MethodologyOut, QueueItem, RegionOut, RegionSummary, RiskCounts
from app.schemas.result import Risk
from app.utils.geojson import region_identifier, region_query

RISK_VALUES = ("normal", "watch", "alert", "cannot_assess")

METHOD_STEPS = [
    "Extract public satellite observations for the configured region and season.",
    "Clean observations by excluding invalid or low-quality measurements.",
    "Align valid observations by date so fields can be compared over time.",
    "Build each field's historical baseline from available observations.",
    "Score current observations against the field's historical baseline.",
    "Evaluate whether an unusual pattern persists and identify its onset.",
    "Add available rainfall context without treating missing rain as zero.",
    "Estimate confidence from the available observation and baseline evidence.",
    "Classify the result using the documented risk vocabulary.",
    "Rank assessable fields to support inspection prioritization.",
]

LIMITATIONS = [
    "An alert means unusual vegetation behaviour, inspect; it is not a claim of crop failure or a diagnosis.",
    "Advice is limited to inspecting or checking the field; the system does not confirm a pest attack or drought.",
    "Synthetic data must be marked is_synthetic=true and is not real-world evidence.",
    "Validation metrics are reported only when produced by pipeline/validate.py.",
]


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


async def get_current_season(database: AsyncIOMotorDatabase) -> dict[str, Any] | None:
    return await database.seasons.find_one(
        {"role": "current"},
        {"_id": 0, "season_id": 1, "label": 1, "start": 1, "end": 1},
    )


async def get_latest_run(database: AsyncIOMotorDatabase) -> dict[str, Any] | None:
    return await database.analysis_runs.find_one(
        {},
        {"_id": 0},
        sort=[("created_at", -1)],
    )


async def get_methodology(database: AsyncIOMotorDatabase) -> MethodologyOut:
    run = await get_latest_run(database)
    if run is None:
        return MethodologyOut(method_steps=METHOD_STEPS.copy(), limitations=LIMITATIONS.copy())

    run_id = run.get("run_id")
    validation_report = None
    if run_id is not None:
        validation_report = await database.validation_reports.find_one(
            {"run_id": run_id},
            {"_id": 0, "run_id": 0},
        )

    return MethodologyOut(
        run_id=run_id,
        params=run.get("params", {}),
        method_steps=METHOD_STEPS.copy(),
        validation_report=validation_report,
        limitations=LIMITATIONS.copy(),
        created_at=run.get("created_at"),
    )


async def get_region_document(
    database: AsyncIOMotorDatabase,
    region_id: str,
) -> dict[str, Any] | None:
    return await database.regions.find_one(region_query(region_id))


async def list_regions(database: AsyncIOMotorDatabase) -> list[RegionOut]:
    documents = await database.regions.find({}).to_list(length=None)
    latest_run = await get_latest_run(database)
    regions: list[RegionOut] = []
    for document in documents:
        region_id = region_identifier(document)
        results = await _get_current_results(database, region_id)
        observation_dates = [
            observation_date
            for result in results
            if (observation_date := _as_date(result.get("latest_obs_date"))) is not None
        ]
        observation_date = max(
            observation_dates,
            default=None,
        )
        regions.append(
            RegionOut(
                region_id=region_id,
                name=document.get("name", ""),
                state=document.get("state"),
                latest_run_id=latest_run.get("run_id") if latest_run else None,
                latest_observation_date=observation_date,
                is_synthetic=latest_run.get("is_synthetic") if latest_run else None,
            )
        )
    return regions


async def _get_current_results(
    database: AsyncIOMotorDatabase,
    region_id: str,
) -> list[dict[str, Any]]:
    season = await get_current_season(database)
    if season is None or not season.get("season_id"):
        return []
    query: dict[str, Any] = {"region_id": region_id, "season_id": season["season_id"]}
    latest_run = await get_latest_run(database)
    if latest_run and latest_run.get("run_id"):
        query["run_id"] = latest_run["run_id"]
    return await database.field_results.find(query, {"_id": 0}).to_list(length=None)


async def get_region_summary(
    database: AsyncIOMotorDatabase,
    region_id: str,
) -> RegionSummary | None:
    region = await get_region_document(database, region_id)
    if region is None:
        return None
    results = await _get_current_results(database, region_id)
    counts = {risk: 0 for risk in RISK_VALUES}
    result_field_ids: set[str] = set()
    for result in results:
        risk = result.get("risk")
        if risk in counts:
            counts[risk] += 1
        if result.get("field_id"):
            result_field_ids.add(str(result["field_id"]))
    fields = await database.fields.find(
        region_query(region_id),
        {"_id": 0, "field_id": 1},
    ).to_list(length=None)
    counts["cannot_assess"] += sum(
        1
        for field in fields
        if field.get("field_id") and str(field["field_id"]) not in result_field_ids
    )
    latest_run = await get_latest_run(database)
    observation_dates = [
        observation_date
        for result in results
        if (observation_date := _as_date(result.get("latest_obs_date"))) is not None
    ]
    latest_date = max(
        observation_dates,
        default=None,
    )
    return RegionSummary(
        region_id=region_identifier(region),
        counts_by_risk=RiskCounts(**counts),
        latest_observation_date=latest_date,
        run_id=latest_run.get("run_id") if latest_run else None,
        is_synthetic=latest_run.get("is_synthetic") if latest_run else None,
    )


async def get_region_fields(
    database: AsyncIOMotorDatabase,
    region_id: str,
) -> list[dict[str, Any]] | None:
    region = await get_region_document(database, region_id)
    if region is None:
        return None
    fields = await database.fields.find(
        region_query(region_id),
        {"_id": 0, "field_id": 1, "name": 1, "geometry": 1, "is_synthetic_boundary": 1},
    ).to_list(length=None)
    result_by_field = {
        result["field_id"]: result
        for result in await _get_current_results(database, region_id)
        if result.get("field_id")
    }
    latest_run = await get_latest_run(database)
    synthetic_run = bool(latest_run and latest_run.get("is_synthetic"))
    features: list[dict[str, Any]] = []
    for field_document in fields:
        field_id = str(field_document.get("field_id", ""))
        result = result_by_field.get(field_id)
        properties = {
            key: value
            for key, value in (result or {}).items()
            if key
            in {
                "risk",
                "severity",
                "confidence",
                "confidence_label",
                "z_score",
                "pct_below_normal",
                "drop_start",
                "latest_obs_date",
                "n_valid_obs",
                "baseline_years",
                "rain_context",
                "advice_key",
                "advice",
                "priority_score",
                "priority_rank",
                "if_flag",
            }
        }
        properties.setdefault("risk", "cannot_assess")
        properties.setdefault("confidence", 0.0)
        properties.setdefault("confidence_label", "low")
        properties.setdefault("n_valid_obs", 0)
        properties.setdefault("baseline_years", 0)
        properties["field_id"] = field_id
        properties["is_synthetic"] = bool(
            result.get("is_synthetic", synthetic_run)
            if result is not None
            else synthetic_run or field_document.get("is_synthetic_boundary", False)
        )
        features.append(
            {
                "type": "Feature",
                "geometry": field_document.get("geometry"),
                "properties": properties,
            }
        )
    return features


async def get_region_queue(
    database: AsyncIOMotorDatabase,
    region_id: str,
    risk: Risk | None,
    limit: int,
) -> list[QueueItem] | None:
    region = await get_region_document(database, region_id)
    if region is None:
        return None
    results = await _get_current_results(database, region_id)
    fields = await database.fields.find(
        region_query(region_id),
        {"_id": 0, "field_id": 1, "name": 1},
    ).to_list(length=None)
    names = {
        str(field["field_id"]): field.get("name")
        for field in fields
        if field.get("field_id")
    }
    latest_run = await get_latest_run(database)
    synthetic_run = bool(latest_run and latest_run.get("is_synthetic"))
    matching = [
        result
        for result in results
        if result.get("field_id") and (risk is None or result.get("risk") == risk)
    ]
    matching.sort(
        key=lambda result: (
            result.get("priority_rank") is None,
            result.get("priority_rank") or 0,
        )
    )
    return [
        QueueItem(
            field_id=str(result["field_id"]),
            name=names.get(str(result["field_id"])),
            risk=result.get("risk", "cannot_assess"),
            severity=result.get("severity"),
            confidence_label=result.get("confidence_label", "low"),
            latest_obs_date=_as_date(result.get("latest_obs_date")),
            priority_rank=result.get("priority_rank"),
            is_synthetic=bool(result.get("is_synthetic", synthetic_run)),
        )
        for result in matching[:limit]
    ]


async def get_methodology(database: AsyncIOMotorDatabase) -> MethodologyOut:
    latest_run = await get_latest_run(database)
    if latest_run is None:
        return MethodologyOut(method_steps=METHOD_STEPS, limitations=LIMITATIONS)
    report = await database.validation_reports.find_one(
        {"run_id": latest_run["run_id"]},
        {"_id": 0, "run_id": 0},
    )
    return MethodologyOut(
        run_id=latest_run.get("run_id"),
        params=latest_run.get("params", {}),
        method_steps=METHOD_STEPS,
        validation_report=report,
        limitations=LIMITATIONS,
        created_at=latest_run.get("created_at"),
    )
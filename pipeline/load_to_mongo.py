"""Idempotently upsert a processed pipeline run into the documented collections."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pymongo import MongoClient, UpdateOne

from .config import config_parameters, season_bounds

_JSON_FIELDS = {"evidence", "top_factors"}


def _native(value: Any) -> Any:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _native(value.item())
    return value


def _records(path: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(path)
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        record = {key: _native(value) for key, value in row.items()}
        for key in _JSON_FIELDS.intersection(record):
            value = record[key]
            if isinstance(value, str):
                try:
                    record[key] = json.loads(value) if value.strip() else None
                except json.JSONDecodeError as error:
                    raise ValueError(f"{key} must contain valid JSON in {path}") from error
        records.append(record)
    return records


def _create_indexes(database: Any) -> None:
    database.fields.create_index(
        [("geometry", "2dsphere")], name="geometry_2dsphere"
    )
    database.fields.create_index("region_id")
    database.fields.create_index("field_id", unique=True)
    database.seasons.create_index("season_id", unique=True)
    database.observations.create_index(
        [("field_id", 1), ("season_id", 1), ("date", 1)], unique=True
    )
    database.rainfall.create_index(
        [("region_id", 1), ("season_id", 1), ("date", 1)]
    )
    database.field_results.create_index(
        [("region_id", 1), ("season_id", 1), ("run_id", 1), ("priority_rank", 1)]
    )
    database.analysis_runs.create_index("run_id", unique=True)
    database.analysis_runs.create_index([("created_at", -1)])
    database.validation_reports.create_index("run_id", unique=True)


def _upsert_many(collection: Any, documents: list[dict[str, Any]], key_fields: tuple[str, ...]) -> None:
    if not documents:
        return
    operations = []
    for document in documents:
        key = {name: document[name] for name in key_fields}
        operations.append(UpdateOne(key, {"$set": document}, upsert=True))
    collection.bulk_write(operations, ordered=False)


def load_processed_run(
    output_dir: Path,
    mongo_uri: str,
    database_name: str,
) -> dict[str, Any]:
    """Load processed outputs; mark the latest run current only after all writes."""
    with (output_dir / "analysis_run.json").open(encoding="utf-8") as source:
        run = json.load(source)
    run_id = str(run["run_id"])
    region_id = str(run["region_id"])
    season_id = str(run.get("season_id") or "")
    if not season_id:
        raise ValueError("analysis_run.json must include the current season_id")
    run["created_at"] = run.get("created_at") or datetime.now(timezone.utc).isoformat()
    run["is_current"] = False
    run.setdefault("model_version", None)
    run.setdefault("model_checksum", None)
    if not isinstance(run.get("params"), dict):
        run["params"] = config_parameters()
    regions_path = output_dir / "fields.geojson"
    with regions_path.open(encoding="utf-8") as source:
        geojson = json.load(source)
    region = dict(geojson.get("region") or {"region_id": region_id, "name": region_id})
    region["region_id"] = region_id
    fields: list[dict[str, Any]] = []
    for feature in geojson.get("features", []):
        properties = dict(feature.get("properties") or {})
        field_id = str(properties["field_id"])
        properties.update(field_id=field_id, region_id=region_id, geometry=feature["geometry"])
        fields.append(properties)

    observations = [
        row
        for row in _records(output_dir / "observations.csv")
        if str(row.get("season_id")) == season_id
    ]
    rainfall = [
        row
        for row in _records(output_dir / "rainfall.csv")
        if str(row.get("season_id")) == season_id
    ]
    field_results = [
        row
        for row in _records(output_dir / "field_results.csv")
        if str(row.get("season_id")) == season_id
    ]
    for document in observations:
        document["run_id"] = run_id
        document["is_synthetic"] = bool(run["is_synthetic"])
    for document in rainfall:
        document.update(region_id=region_id, run_id=run_id)
    for document in field_results:
        document.update(region_id=region_id, run_id=run_id, is_synthetic=bool(run["is_synthetic"]))
        if document.get("model_version") is None:
            document["model_version"] = run["model_version"]
        document.setdefault("model_score", None)
        document.setdefault("top_factors", None)
        document.setdefault("evidence", None)
        document.setdefault("decision_threshold", None)

    seasons: list[dict[str, Any]] = []
    for season_id in sorted({str(row["season_id"]) for row in observations}):
        start, end = season_bounds(season_id)
        seasons.append(
            {
                "season_id": season_id,
                "label": season_id,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "role": "current" if season_id == run["season_id"] else "baseline",
                "is_synthetic": bool(run["is_synthetic"]),
            }
        )
    validation_path = output_dir / "validation_report.json"
    report = None
    if validation_path.exists():
        with validation_path.open(encoding="utf-8") as source:
            candidate_report = json.load(source)
        if candidate_report.get("run_id") == run_id:
            report = candidate_report

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        database = client[database_name]
        _create_indexes(database)

        _upsert_many(database.regions, [region], ("region_id",))
        _upsert_many(database.fields, fields, ("field_id",))
        _upsert_many(database.seasons, seasons, ("season_id",))
        database.observations.delete_many(
            {"field_id": {"$in": [field["field_id"] for field in fields]}}
        )
        database.rainfall.delete_many({"region_id": region_id})
        _upsert_many(database.observations, observations, ("field_id", "season_id", "date"))
        _upsert_many(database.rainfall, rainfall, ("region_id", "date"))
        _upsert_many(
            database.field_results,
            field_results,
            ("field_id", "season_id", "run_id"),
        )
        database.analysis_runs.replace_one({"run_id": run_id}, run, upsert=True)
        if report is not None:
            database.validation_reports.replace_one(
                {"run_id": run_id}, report, upsert=True
            )
        else:
            database.validation_reports.delete_one({"run_id": run_id})

        latest = database.analysis_runs.find_one(sort=[("created_at", -1), ("run_id", 1)])
        database.analysis_runs.update_many({}, {"$set": {"is_current": False}})
        if latest is not None:
            database.analysis_runs.update_one(
                {"run_id": latest["run_id"]}, {"$set": {"is_current": True}}
            )
    finally:
        client.close()
    return {
        "run_id": run_id,
        "regions": 1,
        "fields": len(fields),
        "seasons": len(seasons),
        "observations": len(observations),
        "rainfall": len(rainfall),
        "field_results": len(field_results),
        "validation_report": report is not None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True, help="Processed run directory")
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    parser.add_argument("--database", default=os.getenv("MONGODB_DB", "cropshield"))
    args = parser.parse_args()
    print(load_processed_run(args.data_dir, args.mongo_uri, args.database))


if __name__ == "__main__":
    main()
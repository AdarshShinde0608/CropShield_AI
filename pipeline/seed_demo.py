"""Build and load a clearly synthetic CropShield demo dataset.

Run from the repository root with:
    python -m pipeline.seed_demo
"""

from __future__ import annotations

import argparse
import math
import os
import random
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

from .config import (
    BASELINE_SEASON_COUNT,
    BASELINE_START_YEAR,
    CLOUD_GAP_PROBABILITY,
    CLOUDY_FIELD_COUNT,
    CLOUDY_FIELD_GAP_PROBABILITY,
    CLOUDY_FIELD_VALID_FRACTION_MAX,
    CONFIDENCE_MAX,
    CURRENT_SEASON_START_YEAR,
    DRY_SPELL_END_DOS,
    DRY_SPELL_RAIN_MM_PER_DAY,
    DRY_SPELL_START_DOS,
    FIELD_COUNT,
    FIELD_AREA_SQUARE_METERS_PER_HECTARE,
    FIELD_ID_PAD_WIDTH,
    FIELD_NAME_PAD_WIDTH,
    FIELD_GRID_COLUMNS,
    FIELD_GRID_SPACING_METERS,
    FIELD_OFFSET_CENTER,
    FIELD_OFFSET_MODULUS,
    FIELD_OFFSET_STEP,
    FIELD_SIDE_METERS,
    MAX_NDVI,
    MAX_CLOUD_GAP_VALID_FRACTION,
    MAXIMUM_NORMAL_VALID_FRACTION,
    METERS_PER_LATITUDE_DEGREE,
    MINIMUM_CLOUD_VALID_FRACTION,
    MINIMUM_NORMAL_VALID_FRACTION,
    MINIMUM_SEASON_LENGTH_DAYS,
    MINIMUM_VALID_FRACTION,
    MIN_RAIN_MM,
    MIN_NDVI,
    NDVI_AT_HARVEST,
    NDVI_AT_PEAK,
    NDVI_AT_SOWING,
    NORMAL_NOISE_MAX_ABSOLUTE,
    NORMAL_RAIN_MM_PER_DAY,
    OUTPUT_DECIMAL_PLACES as SEED_OUTPUT_DECIMAL_PLACES,
    RAIN_DECIMAL_PLACES,
    RAINFALL_14_DAY_WINDOW,
    RAINFALL_30_DAY_WINDOW,
    RAINFALL_STEP_DAYS,
    SEED_RUN_ID,
    SEED_RUN_NOTES,
    OBSERVATION_INTERVAL_DAYS,
    OBSERVATION_DECIMAL_PLACES,
    PEAK_DAY_OF_SEASON,
    REGION_CENTER_LATITUDE,
    REGION_CENTER_LONGITUDE,
    REGION_ID,
    REGION_NAME,
    REGION_STATE,
    SEED_SEASON_END_DAY,
    SEED_SEASON_END_MONTH,
    SEED_SEASON_START_DAY,
    SEED_SEASON_START_MONTH,
    SEED_VALUE,
    SECTION_5_COLLECTIONS,
    STRESS_FIELD_COUNT,
    STRESS_REDUCTION_DENOMINATOR,
    STRESS_PCT_REDUCTIONS,
    STRESS_START_DAYS_OF_SEASON,
    config_parameters,
    seed_parameters,
)
from .baseline import build_baseline
from .clean import clean_observations
from .confidence import apply_confidence
from .config import PIPELINE_CONFIG
from .context import add_rain_context, compute_rainfall_features
from .score import rank_results, score_current


def _season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _season_dates(start_year: int) -> tuple[date, date]:
    start = date(start_year, SEED_SEASON_START_MONTH, SEED_SEASON_START_DAY)
    end = date(start_year + 1, SEED_SEASON_END_MONTH, SEED_SEASON_END_DAY)
    return start, end


def _day_of_season_values(season_length: int) -> list[int]:
    days = list(range(1, season_length + 1, OBSERVATION_INTERVAL_DAYS))
    if days[-1] != season_length:
        days.append(season_length)
    return days


def _base_ndvi(dos: int, field_offset: float) -> float:
    if dos <= PEAK_DAY_OF_SEASON:
        fraction = dos / PEAK_DAY_OF_SEASON
        shape = math.sin(fraction * math.pi / 2)
        return NDVI_AT_SOWING + (NDVI_AT_PEAK - NDVI_AT_SOWING) * shape + field_offset
    decline_days = MINIMUM_SEASON_LENGTH_DAYS - PEAK_DAY_OF_SEASON
    fraction = (dos - PEAK_DAY_OF_SEASON) / decline_days
    shape = math.cos(fraction * math.pi / 2)
    return NDVI_AT_HARVEST + (NDVI_AT_PEAK - NDVI_AT_HARVEST) * shape + field_offset


def _field_geometry(field_number: int) -> dict[str, Any]:
    row, column = divmod(field_number, FIELD_GRID_COLUMNS)
    grid_rows = math.ceil(FIELD_COUNT / FIELD_GRID_COLUMNS)
    x_meters = (column - (FIELD_GRID_COLUMNS - 1) / 2) * FIELD_GRID_SPACING_METERS
    y_meters = (row - (grid_rows - 1) / 2) * FIELD_GRID_SPACING_METERS
    latitude = REGION_CENTER_LATITUDE + y_meters / METERS_PER_LATITUDE_DEGREE
    meters_per_longitude_degree = (
        METERS_PER_LATITUDE_DEGREE * math.cos(math.radians(REGION_CENTER_LATITUDE))
    )
    longitude = REGION_CENTER_LONGITUDE + x_meters / meters_per_longitude_degree
    half_latitude = FIELD_SIDE_METERS / (2 * METERS_PER_LATITUDE_DEGREE)
    half_longitude = FIELD_SIDE_METERS / (2 * meters_per_longitude_degree)
    ring = [
        [longitude - half_longitude, latitude - half_latitude],
        [longitude + half_longitude, latitude - half_latitude],
        [longitude + half_longitude, latitude + half_latitude],
        [longitude - half_longitude, latitude + half_latitude],
        [longitude - half_longitude, latitude - half_latitude],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def _region_document() -> dict[str, Any]:
    half_grid_x = (FIELD_GRID_COLUMNS - 1) * FIELD_GRID_SPACING_METERS / 2
    grid_rows = math.ceil(FIELD_COUNT / FIELD_GRID_COLUMNS)
    half_grid_y = (grid_rows - 1) * FIELD_GRID_SPACING_METERS / 2
    half_field = FIELD_SIDE_METERS / 2
    meters_per_longitude_degree = (
        METERS_PER_LATITUDE_DEGREE * math.cos(math.radians(REGION_CENTER_LATITUDE))
    )
    half_lat = (half_grid_y + half_field) / METERS_PER_LATITUDE_DEGREE
    half_lon = (half_grid_x + half_field) / meters_per_longitude_degree
    return {
        "region_id": REGION_ID,
        "name": REGION_NAME,
        "state": REGION_STATE,
        "bbox": [
            REGION_CENTER_LONGITUDE - half_lon,
            REGION_CENTER_LATITUDE - half_lat,
            REGION_CENTER_LONGITUDE + half_lon,
            REGION_CENTER_LATITUDE + half_lat,
        ],
        "centroid": {
            "type": "Point",
            "coordinates": [REGION_CENTER_LONGITUDE, REGION_CENTER_LATITUDE],
        },
        "is_synthetic": True,
        "synthetic_notice": SEED_RUN_NOTES,
    }


def _field_documents() -> list[dict[str, Any]]:
    area_hectares = (
        FIELD_SIDE_METERS
        * FIELD_SIDE_METERS
        / FIELD_AREA_SQUARE_METERS_PER_HECTARE
    )
    fields = []
    for index in range(FIELD_COUNT):
        fields.append(
            {
                "field_id": f"demo-field-{index + 1:0{FIELD_ID_PAD_WIDTH}d}",
                "region_id": REGION_ID,
                "name": f"Demo Field {index + 1:0{FIELD_NAME_PAD_WIDTH}d}",
                "geometry": _field_geometry(index),
                "area_ha": area_hectares,
                "is_synthetic_boundary": True,
                "is_synthetic": True,
            }
        )
    return fields


def _season_documents() -> tuple[list[dict[str, Any]], str]:
    years = list(range(BASELINE_START_YEAR, BASELINE_START_YEAR + BASELINE_SEASON_COUNT))
    years.append(CURRENT_SEASON_START_YEAR)
    current_season_id = _season_label(CURRENT_SEASON_START_YEAR)
    documents = []
    for year in years:
        start, end = _season_dates(year)
        documents.append(
            {
                "season_id": _season_label(year),
                "label": _season_label(year),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "role": "current" if year == CURRENT_SEASON_START_YEAR else "baseline",
                "is_synthetic": True,
            }
        )
    return documents, current_season_id


def _rainfall_documents(
    start: date,
    end: date,
    seed: int,
    season_id: str,
    dry_spell: bool,
) -> list[dict[str, Any]]:
    rng = random.Random(seed + sum(start.timetuple()[:3]))
    documents = []
    current = start
    while current <= end:
        dos = (current - start).days + 1
        in_dry_spell = dry_spell and DRY_SPELL_START_DOS <= dos <= DRY_SPELL_END_DOS
        rain_mm = rng.uniform(
            MIN_RAIN_MM,
            DRY_SPELL_RAIN_MM_PER_DAY if in_dry_spell else NORMAL_RAIN_MM_PER_DAY,
        )
        documents.append(
            {
                "region_id": REGION_ID,
                "season_id": season_id,
                "date": current.isoformat(),
                "dos": dos,
                "rain_mm": round(rain_mm, RAIN_DECIMAL_PLACES),
                "rain14": None,
                "rain30": None,
                "rain_z": None,
                "source": "CHIRPS-like synthetic rainfall; not CHIRPS observations",
                "is_synthetic": True,
            }
        )
        current += timedelta(days=RAINFALL_STEP_DAYS)
    for index, document in enumerate(documents):
        window_14 = documents[max(0, index - RAINFALL_14_DAY_WINDOW + 1) : index + 1]
        window_30 = documents[max(0, index - RAINFALL_30_DAY_WINDOW + 1) : index + 1]
        document["rain14"] = round(
            sum(item["rain_mm"] for item in window_14),
            RAIN_DECIMAL_PLACES,
        )
        document["rain30"] = round(
            sum(item["rain_mm"] for item in window_30),
            RAIN_DECIMAL_PLACES,
        )
    return documents


def _is_cloudy_field(field_index: int) -> bool:
    return field_index >= FIELD_COUNT - CLOUDY_FIELD_COUNT


def _current_season_observations(
    fields: list[dict[str, Any]],
    season_id: str,
    day_values: list[int],
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed + 2)
    start, _ = _season_dates(CURRENT_SEASON_START_YEAR)
    observations: list[dict[str, Any]] = []

    for field_index, field in enumerate(fields):
        field_id = field["field_id"]
        cloudy = _is_cloudy_field(field_index)
        is_stressed = field_index < STRESS_FIELD_COUNT
        stress_start = STRESS_START_DAYS_OF_SEASON[field_index] if is_stressed else None
        reduction = (
            STRESS_PCT_REDUCTIONS[field_index] / STRESS_REDUCTION_DENOMINATOR
            if is_stressed
            else 0.0
        )
        field_offset = (
            (field_index % FIELD_OFFSET_MODULUS) - FIELD_OFFSET_CENTER
        ) * FIELD_OFFSET_STEP

        for dos in day_values:
            cloud_gap = rng.random() < (
                CLOUDY_FIELD_GAP_PROBABILITY if cloudy else CLOUD_GAP_PROBABILITY
            )
            date_value = start + timedelta(days=dos - 1)
            valid_fraction = (
                rng.uniform(MINIMUM_CLOUD_VALID_FRACTION, CLOUDY_FIELD_VALID_FRACTION_MAX)
                if cloudy
                else rng.uniform(
                    MINIMUM_NORMAL_VALID_FRACTION,
                    MAXIMUM_NORMAL_VALID_FRACTION,
                )
            )
            if cloud_gap:
                valid_fraction = min(valid_fraction, MAX_CLOUD_GAP_VALID_FRACTION)
                ndvi = None
            else:
                ndvi_value = _base_ndvi(dos, field_offset) + rng.uniform(
                    -NORMAL_NOISE_MAX_ABSOLUTE,
                    NORMAL_NOISE_MAX_ABSOLUTE,
                )
                if stress_start is not None and dos >= stress_start:
                    ndvi_value *= CONFIDENCE_MAX - reduction
                ndvi = round(
                    max(MIN_NDVI, min(MAX_NDVI, ndvi_value)),
                    SEED_OUTPUT_DECIMAL_PLACES,
                )

            observation = {
                "field_id": field_id,
                "season_id": season_id,
                "date": date_value.isoformat(),
                "dos": dos,
                "ndvi": ndvi,
                "valid_frac": round(valid_fraction, OBSERVATION_DECIMAL_PLACES),
                "is_interpolated": False,
                "low_quality": valid_fraction < MINIMUM_VALID_FRACTION,
                "is_synthetic": True,
            }
            observations.append(observation)

    return observations


def build_seed_data(seed: int = SEED_VALUE) -> dict[str, list[dict[str, Any]]]:
    """Create all synthetic analytical documents without connecting to MongoDB."""
    season_documents, current_season_id = _season_documents()
    current_start, current_end = _season_dates(CURRENT_SEASON_START_YEAR)
    season_length = min(
        MINIMUM_SEASON_LENGTH_DAYS,
        (current_end - current_start).days + 1,
    )
    day_values = _day_of_season_values(season_length)
    fields = _field_documents()

    observations: list[dict[str, Any]] = []
    for field_index, field in enumerate(fields):
        field_id = field["field_id"]
        field_rng = random.Random(seed + field_index)
        field_offset = (
            (field_index % FIELD_OFFSET_MODULUS) - FIELD_OFFSET_CENTER
        ) * FIELD_OFFSET_STEP
        for year in range(BASELINE_START_YEAR, BASELINE_START_YEAR + BASELINE_SEASON_COUNT):
            start, _ = _season_dates(year)
            for dos in day_values:
                cloudy = _is_cloudy_field(field_index)
                cloud_gap = field_rng.random() < (
                    CLOUDY_FIELD_GAP_PROBABILITY if cloudy else CLOUD_GAP_PROBABILITY
                )
                valid_fraction = (
                    field_rng.uniform(
                        MINIMUM_CLOUD_VALID_FRACTION,
                        CLOUDY_FIELD_VALID_FRACTION_MAX,
                    )
                    if cloudy
                    else field_rng.uniform(
                        MINIMUM_NORMAL_VALID_FRACTION,
                        MAXIMUM_NORMAL_VALID_FRACTION,
                    )
                )
                value = None
                if not cloud_gap:
                    value = round(
                        max(
                            MIN_NDVI,
                            min(
                                MAX_NDVI,
                                _base_ndvi(dos, field_offset)
                                + field_rng.uniform(
                                    -NORMAL_NOISE_MAX_ABSOLUTE,
                                    NORMAL_NOISE_MAX_ABSOLUTE,
                                ),
                            ),
                        ),
                        SEED_OUTPUT_DECIMAL_PLACES,
                    )
                else:
                    valid_fraction = min(
                        valid_fraction,
                        MAX_CLOUD_GAP_VALID_FRACTION,
                    )
                observations.append(
                    {
                        "field_id": field_id,
                        "season_id": _season_label(year),
                        "date": (start + timedelta(days=dos - 1)).isoformat(),
                        "dos": dos,
                        "ndvi": value,
                        "valid_frac": round(valid_fraction, 3),
                        "baseline_median": None,
                        "baseline_sigma": None,
                        "z": None,
                        "pct_dev": None,
                        "is_interpolated": False,
                        "low_quality": valid_fraction < MINIMUM_VALID_FRACTION,
                        "is_synthetic": True,
                    }
                )
    current_observations_raw = _current_season_observations(
        fields,
        current_season_id,
        day_values,
        seed,
    )
    raw = pd.DataFrame(observations)
    clean = clean_observations(raw, PIPELINE_CONFIG)
    baseline_seasons = [
        season["season_id"] for season in season_documents if season["role"] == "baseline"
    ]
    baseline, clusters = build_baseline(clean, baseline_seasons, PIPELINE_CONFIG)
    for field in fields:
        field["cluster"] = clusters.get(str(field["field_id"]), 0)

    current_frame = pd.DataFrame(current_observations_raw)
    current_clean = clean_observations(current_frame, PIPELINE_CONFIG)
    clean_keys = set(
        zip(
            current_clean["field_id"].astype(str),
            current_clean["date"],
        )
    )
    current_frame["date"] = pd.to_datetime(current_frame["date"]).dt.date
    current_frame["field_id"] = current_frame["field_id"].astype(str)
    usable = [
        (str(row.field_id), row.date) in clean_keys
        for row in current_frame.itertuples()
    ]
    current_frame.loc[~pd.Series(usable, index=current_frame.index), "ndvi"] = None
    current_frame.loc[~pd.Series(usable, index=current_frame.index), "low_quality"] = True
    scored_current, results = score_current(current_frame, baseline, PIPELINE_CONFIG)

    rainfall_documents: list[dict[str, Any]] = []
    for season in season_documents:
        start, end = _season_dates(int(season["season_id"].split("-")[0]))
        rainfall_documents.extend(
            _rainfall_documents(
                start,
                end,
                seed,
                season["season_id"],
                season["role"] == "current",
            )
        )
    rainfall_features = compute_rainfall_features(
        pd.DataFrame(rainfall_documents),
        baseline_seasons,
        PIPELINE_CONFIG,
    )
    results = add_rain_context(results, rainfall_features, PIPELINE_CONFIG)
    results = apply_confidence(scored_current, results, current_end, PIPELINE_CONFIG)
    results = rank_results(results, pd.DataFrame(fields), PIPELINE_CONFIG)

    scored_by_key = {
        (str(row.field_id), row.date): row._asdict()
        for row in scored_current.itertuples(index=False)
    }
    current_observation_documents = []
    for observation in current_observations_raw:
        key = (str(observation["field_id"]), date.fromisoformat(observation["date"]))
        scores = scored_by_key.get(key, {})
        current_observation_documents.append(
            {
                **observation,
                "baseline_median": scores.get("baseline_median"),
                "baseline_sigma": scores.get("baseline_sigma"),
                "baseline_years": scores.get("baseline_years"),
                "z": scores.get("z"),
                "pct_dev": scores.get("pct_dev"),
                "cluster": scores.get("cluster"),
                "is_synthetic": True,
            }
        )
    observations = [
        {
            **observation,
            "date": (
                observation["date"].isoformat()
                if isinstance(observation["date"], date)
                else observation["date"]
            ),
        }
        for observation in current_observation_documents
    ]
    rainfall_documents = []
    for row in rainfall_features.to_dict(orient="records"):
        if str(row.get("season_id")) != current_season_id:
            continue
        rainfall_documents.append(
            {
                **row,
                "date": (
                    row["date"].isoformat()
                    if isinstance(row["date"], date)
                    else row["date"]
                ),
                **{
                    key: float(row[key]) if pd.notna(row[key]) else None
                    for key in ("rain_mm", "rain14", "rain30", "rain_z")
                },
                "is_synthetic": True,
            }
        )
    for result in results:
        result.update(
            region_id=REGION_ID,
            season_id=current_season_id,
            run_id=SEED_RUN_ID,
            is_synthetic=True,
        )
        for key in ("drop_start", "latest_obs_date"):
            if isinstance(result.get(key), date):
                result[key] = result[key].isoformat()
        result.pop("run_length", None)
        result.pop("baseline_median", None)
        result.pop("baseline_sigma", None)
    parameters = seed_parameters(seed)
    parameters.update(config_parameters(PIPELINE_CONFIG))
    parameters["baseline_season_count"] = BASELINE_SEASON_COUNT
    for field in fields:
        field.pop("is_synthetic", None)
    return {
        "users": [],
        "regions": [_region_document()],
        "fields": fields,
        "seasons": season_documents,
        "observations": observations,
        "rainfall": rainfall_documents,
        "field_results": results,
        "analysis_runs": [
            {
                "run_id": SEED_RUN_ID,
                "created_at": datetime.now(timezone.utc),
                "season_id": current_season_id,
                "model_version": None,
                "model_checksum": None,
                "params": parameters,
                "is_synthetic": True,
                "n_fields": FIELD_COUNT,
                "notes": SEED_RUN_NOTES,
            }
        ],
        "validation_reports": [],
        "actions": [],
    }


def load_seed_data(database: Any, documents: dict[str, list[dict[str, Any]]]) -> None:
    """Replace only this demo region's data; preserve users and actions."""
    existing_region_ids = {
        document["region_id"]
        for document in database.regions.find({}, {"_id": 0, "region_id": 1})
        if document.get("region_id") and document["region_id"] != REGION_ID
    }
    if existing_region_ids:
        raise RuntimeError(
            "Refusing to seed a database containing other regions; use an isolated demo database."
        )

    existing_collections = set(database.list_collection_names())
    for collection_name in SECTION_5_COLLECTIONS:
        if collection_name not in existing_collections:
            database.create_collection(collection_name)

    field_ids = [field["field_id"] for field in documents["fields"]]
    database.regions.replace_one(
        {"region_id": REGION_ID},
        documents["regions"][0],
        upsert=True,
    )
    database.fields.delete_many({"region_id": REGION_ID})
    if documents["fields"]:
        database.fields.insert_many(documents["fields"])

    database.seasons.update_many({"role": "current"}, {"$set": {"role": "baseline"}})
    for season in documents["seasons"]:
        database.seasons.replace_one(
            {"season_id": season["season_id"]},
            season,
            upsert=True,
        )

    database.observations.delete_many({"field_id": {"$in": field_ids}})
    if documents["observations"]:
        database.observations.insert_many(documents["observations"])
    database.rainfall.delete_many({"region_id": REGION_ID})
    if documents["rainfall"]:
        database.rainfall.insert_many(documents["rainfall"])
    database.field_results.delete_many({"region_id": REGION_ID})
    if documents["field_results"]:
        database.field_results.insert_many(documents["field_results"])
    database.analysis_runs.replace_one(
        {"run_id": SEED_RUN_ID},
        documents["analysis_runs"][0],
        upsert=True,
    )
    database.validation_reports.delete_many({"run_id": SEED_RUN_ID})


def _risk_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(result["risk"] for result in results))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
    )
    parser.add_argument(
        "--database",
        default=os.getenv("MONGODB_DB", "cropshield"),
    )
    args = parser.parse_args()

    from pymongo import MongoClient

    documents = build_seed_data()
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000) as client:
        client.admin.command("ping")
        database = client[args.database]
        load_seed_data(database, documents)
    print(
        f"Loaded {len(documents['fields'])} synthetic fields, "
        f"{len(documents['observations'])} observations; "
        f"risk counts={_risk_summary(documents['field_results'])}. "
        "No validation report was fabricated."
    )


if __name__ == "__main__":
    main()
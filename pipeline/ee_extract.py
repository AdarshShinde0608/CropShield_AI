"""Authenticated Sentinel-2 and CHIRPS extraction from Earth Engine."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, TypeVar

import pandas as pd

from .config import PIPELINE_CONFIG, PipelineConfig, season_bounds

T = TypeVar("T")


def initialize_earth_engine() -> Any:
    """Initialize Earth Engine with an environment-configured service account."""
    project = os.getenv("GEE_PROJECT")
    service_account = os.getenv("GEE_SERVICE_ACCOUNT")
    key_file = os.getenv("GEE_KEY_FILE")
    if not project or not service_account or not key_file:
        raise RuntimeError("GEE_PROJECT, GEE_SERVICE_ACCOUNT, and GEE_KEY_FILE are required")
    if not Path(key_file).is_file():
        raise FileNotFoundError("GEE_KEY_FILE does not point to a readable service-account key")
    try:
        import ee
    except ImportError as exc:
        raise RuntimeError("Install the pipeline Earth Engine dependencies first") from exc
    credentials = ee.ServiceAccountCredentials(service_account, key_file)
    ee.Initialize(credentials, project=project)
    return ee


def retry_earth_engine(
    operation: Callable[[], T],
    config: PipelineConfig = PIPELINE_CONFIG,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retry a remote Earth Engine operation with bounded exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(config.ee_retry_count):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt + 1 == config.ee_retry_count:
                break
            sleep(config.ee_retry_base_seconds * (2**attempt))
    if last_error is None:
        raise RuntimeError("Earth Engine retry count must be positive")
    raise RuntimeError("Earth Engine request failed after retries") from last_error


def _load_fields(ee: Any, fields_path: Path) -> tuple[Any, list[dict[str, Any]]]:
    with fields_path.open(encoding="utf-8") as source:
        geojson = json.load(source)
    features = geojson.get("features", []) if geojson.get("type") == "FeatureCollection" else []
    if not features:
        raise ValueError("fields input must be a non-empty GeoJSON FeatureCollection")
    ee_features = []
    for feature in features:
        properties = feature.get("properties") or {}
        field_id = properties.get("field_id")
        if not field_id:
            raise ValueError("every field feature must include properties.field_id")
        ee_features.append(
            ee.Feature(ee.Geometry(feature["geometry"]), {"field_id": str(field_id)})
        )
    return ee.FeatureCollection(ee_features), features


def _extract_ndvi(
    ee: Any,
    fields: Any,
    start: date,
    end: date,
    config: PipelineConfig,
) -> list[dict[str, Any]]:
    field_geometry = fields.geometry()
    cloud_score = (
        ee.ImageCollection(config.cloud_score_collection_id)
        .filterBounds(field_geometry)
        .filterDate(start.isoformat(), (end + timedelta(days=1)).isoformat())
    )
    sentinel = (
        ee.ImageCollection(config.sentinel_collection_id)
        .filterBounds(field_geometry)
        .filterDate(start.isoformat(), (end + timedelta(days=1)).isoformat())
    )
    joined = ee.ImageCollection(
        ee.Join.saveFirst("cloud_score_image").apply(
            primary=sentinel,
            secondary=cloud_score,
            condition=ee.Filter.equals(
                leftField="system:index", rightField="system:index"
            ),
        )
    ).filter(ee.Filter.notNull(["cloud_score_image"]))
    crop_pixels = (
        ee.ImageCollection(config.worldcover_collection_id)
        .mosaic()
        .select("Map")
        .eq(config.worldcover_cropland_class)
        .unmask(0)
        .clip(field_geometry)
    )
    chunks: list[dict[str, Any]] = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(
            chunk_start + timedelta(days=config.extraction_chunk_days),
            end + timedelta(days=1),
        )

        def fetch_chunk() -> list[dict[str, Any]]:
            period = joined.filterDate(chunk_start.isoformat(), chunk_end.isoformat())

            def prepare(image: Any) -> Any:
                score = ee.Image(image.get("cloud_score_image"))
                clear = (
                    score.select("cs_cdf")
                    .gte(config.cs_threshold)
                    .unmask(0, False)
                    .clip(field_geometry)
                )
                crop = crop_pixels.eq(1)
                ndvi = (
                    image.updateMask(clear)
                    .updateMask(crop)
                    .normalizedDifference(["B8", "B4"])
                    .rename("ndvi")
                )
                valid = clear.updateMask(crop).rename("valid_frac")
                return ndvi.addBands(valid).copyProperties(image, ["system:time_start"])

            date_labels = ee.List(
                period.aggregate_array("system:time_start")
            ).map(lambda stamp: ee.Date(stamp).format("YYYY-MM-dd")).distinct()

            def mosaic_date(label: Any) -> Any:
                day = ee.Date.parse("YYYY-MM-dd", label)
                next_day = day.advance(1, "day")
                daily_tiles = period.filterDate(day, next_day).map(prepare)
                ndvi = daily_tiles.select("ndvi").mosaic()
                valid = daily_tiles.select("valid_frac").max()
                return ndvi.addBands(valid).set("system:time_start", day.millis())

            daily_mosaics = ee.ImageCollection.fromImages(date_labels.map(mosaic_date))
            composite = daily_mosaics.select("ndvi").median().addBands(
                daily_mosaics.select("valid_frac").mean()
            )
            reduced = composite.reduceRegions(
                collection=fields,
                reducer=ee.Reducer.median().combine(
                    ee.Reducer.mean(), sharedInputs=False
                ),
                scale=config.sentinel_scale_meters,
            )
            return reduced.getInfo()["features"]

        features = retry_earth_engine(fetch_chunk, config)
        for item in features:
            properties = item.get("properties") or {}
            valid_frac = properties.get("valid_frac_mean")
            if valid_frac is None:
                valid_frac = 0.0
            chunks.append(
                {
                    "field_id": str(properties["field_id"]),
                    "date": chunk_start.isoformat(),
                    "dos": (chunk_start - start).days + 1,
                    "ndvi": properties.get("ndvi_median"),
                    "valid_frac": min(1.0, max(0.0, valid_frac)),
                    "low_quality": valid_frac < config.min_valid_frac,
                    "is_interpolated": False,
                }
            )
        chunk_start = chunk_end
    return chunks


def _extract_rainfall(
    ee: Any,
    fields: Any,
    start: date,
    end: date,
    config: PipelineConfig,
) -> list[dict[str, Any]]:
    geometry = fields.geometry()
    daily = ee.ImageCollection(config.chirps_collection_id)
    output: list[dict[str, Any]] = []
    current = start
    while current <= end:
        next_day = current + timedelta(days=1)

        def fetch_day() -> float | None:
            image = daily.filterDate(current.isoformat(), next_day.isoformat()).first()
            if image is None:
                return None
            value = ee.Image(image).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=config.chirps_scale_meters,
                maxPixels=config.gee_max_pixels,
            ).get("precipitation")
            return value.getInfo()

        output.append(
            {
                "date": current.isoformat(),
                "rain_mm": retry_earth_engine(fetch_day, config),
            }
        )
        current = next_day
    return output


def extract_season(
    fields_path: Path,
    output_dir: Path,
    season_label: str,
    ee: Any | None = None,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> tuple[Path, Path] | None:
    """Extract one configured season; return None when both CSVs already exist."""
    output_dir.mkdir(parents=True, exist_ok=True)
    start, end = season_bounds(season_label)
    suffix = season_label.replace("-", "_")
    ndvi_path = output_dir / f"ndvi_{suffix}.csv"
    rainfall_path = output_dir / f"rain_{suffix}.csv"
    if ndvi_path.exists() and rainfall_path.exists():
        return None
    engine = ee or initialize_earth_engine()
    field_collection, _ = _load_fields(engine, fields_path)
    if not ndvi_path.exists():
        pd.DataFrame(_extract_ndvi(engine, field_collection, start, end, config)).to_csv(
            ndvi_path, index=False
        )
    if not rainfall_path.exists():
        pd.DataFrame(_extract_rainfall(engine, field_collection, start, end, config)).to_csv(
            rainfall_path, index=False
        )
    return ndvi_path, rainfall_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields", required=True, type=Path, help="Input fields GeoJSON")
    parser.add_argument("--out", required=True, type=Path, help="Output directory")
    parser.add_argument(
        "--seasons",
        required=True,
        nargs="+",
        help="Season labels such as 2019-20 2025-26",
    )
    args = parser.parse_args()
    ee = initialize_earth_engine()
    for label in args.seasons:
        result = extract_season(args.fields, args.out, label, ee)
        if result is None:
            print(f"Skipping {label}: season CSVs already exist")
        else:
            print(f"Extracted {label}: {result[0].name}, {result[1].name}")


if __name__ == "__main__":
    main()
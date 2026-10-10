"""Run the offline CropShield analysis pipeline from extracted CSVs."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .baseline import build_baseline
from .clean import clean_observations, regularize_observations
from .confidence import apply_confidence
from .config import (
    PIPELINE_CONFIG,
    PipelineConfig,
    config_parameters,
    day_of_season,
    season_bounds,
)
from .context import add_rain_context, compute_rainfall_features
from .score import rank_results, score_current
from .validate import validate_pipeline


def _season_from_filename(path: Path) -> str:
    suffix = path.stem.rsplit("_", maxsplit=2)
    if len(suffix) < 3:
        raise ValueError(f"Cannot infer season label from {path.name}")
    return f"{suffix[-2].replace('_', '-')}-{suffix[-1]}"


def _load_csv_seasons(data_dir: Path, prefix: str) -> pd.DataFrame:
    paths = sorted(data_dir.glob(f"{prefix}_*.csv"))
    if not paths:
        raise FileNotFoundError(f"No {prefix}_*.csv files found in {data_dir}")
    frames: list[pd.DataFrame] = []
    for path in paths:
        label = _season_from_filename(path)
        frame = pd.read_csv(path)
        frame["season_id"] = frame.get("season_id", label)
        if "dos" not in frame:
            start, _ = season_bounds(label)
            frame["dos"] = [
                day_of_season(pd.Timestamp(value).date(), start)
                for value in frame["date"]
            ]
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _load_geojson_fields(path: Path, region_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        geojson = json.load(source)
    features = geojson.get("features", [])
    if not features:
        raise ValueError("fields.geojson must contain at least one feature")
    fields: list[dict[str, Any]] = []
    for feature in features:
        properties = dict(feature.get("properties") or {})
        field_id = properties.get("field_id")
        if not field_id:
            raise ValueError("every feature must define properties.field_id")
        fields.append(
            {
                **properties,
                "field_id": str(field_id),
                "region_id": region_id,
                "geometry": feature["geometry"],
            }
        )
    region = geojson.get("region") or {
        "region_id": region_id,
        "name": region_id,
        "state": None,
    }
    region["region_id"] = region_id
    return fields, region


def _clean_all_seasons(
    observations: pd.DataFrame,
    config: PipelineConfig,
) -> pd.DataFrame:
    cleaned = clean_observations(observations, config)
    keys = [key for key in ("field_id", "season_id", "date") if key in observations]
    clean_keys = cleaned[keys].drop_duplicates()
    frame = observations.copy(deep=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    clean_keys = clean_keys.copy()
    clean_keys["date"] = pd.to_datetime(clean_keys["date"], errors="coerce").dt.date
    frame = frame.merge(clean_keys.assign(_usable=True), on=keys, how="left")
    frame["ndvi"] = pd.to_numeric(frame["ndvi"], errors="coerce")
    frame.loc[frame["_usable"].isna(), "ndvi"] = float("nan")
    frame["low_quality"] = frame.get(
        "low_quality", pd.Series(False, index=frame.index)
    ).fillna(False).astype(bool) | frame["_usable"].isna()
    frame = frame.drop(columns=["_usable"])
    interpolated = regularize_observations(cleaned, config)
    combined = pd.concat([frame, interpolated], ignore_index=True)
    combined = combined.drop_duplicates(
        [key for key in ("field_id", "season_id", "date") if key in combined],
        keep="last",
    )
    return combined.sort_values(
        [key for key in ("field_id", "season_id", "date") if key in combined],
        kind="stable",
    ).reset_index(drop=True)


def run_pipeline(
    data_dir: Path,
    region_id: str,
    run_id: str,
    skip_validation: bool = False,
    is_synthetic: bool | None = None,
    as_of: date | None = None,
    output_dir: Path | None = None,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> dict[str, Any]:
    """Execute stages, persist processed CSV/JSON artifacts, and return run data."""
    fields_path = data_dir / "fields.geojson"
    fields, region = _load_geojson_fields(fields_path, region_id)
    observations = _load_csv_seasons(data_dir, "ndvi")
    rainfall = _load_csv_seasons(data_dir, "rain")
    available_seasons = set(observations["season_id"].astype(str).unique())
    baseline_ids = [season for season in config.baseline_seasons if season in available_seasons]
    current_season = config.current_season
    if current_season not in available_seasons:
        raise ValueError(f"Current season {current_season} has no matching NDVI CSV")
    if len(baseline_ids) < 1:
        raise ValueError("No configured baseline seasons are present in the input data")

    cleaned = _clean_all_seasons(observations, config)
    baseline, clusters = build_baseline(cleaned, baseline_ids, config)
    for field in fields:
        field["cluster"] = clusters.get(str(field["field_id"]), 0)
    current = cleaned.loc[cleaned["season_id"].astype(str) == current_season].copy()
    scored_current, results = score_current(current, baseline, config)
    rainfall["season_id"] = rainfall.get("season_id", None)
    if rainfall["season_id"].isna().all():
        rainfall["season_id"] = [
            _season_from_filename(Path(f"rain_{value}.csv"))
            for value in rainfall.get("source_file", pd.Series(index=rainfall.index, dtype=str))
        ]
    rain_features = compute_rainfall_features(rainfall, baseline_ids, config)
    rain_by_date = rain_features[["season_id", "date", "rain_z"]].drop_duplicates(
        ["season_id", "date"]
    )
    scored_current = scored_current.merge(
        rain_by_date,
        on=["season_id", "date"],
        how="left",
        validate="many_to_one",
    )
    synthetic_from_data = bool(
        observations.get("is_synthetic", pd.Series(False, index=observations.index))
        .fillna(False)
        .astype(bool)
        .all()
    )
    synthetic = synthetic_from_data if is_synthetic is None else is_synthetic
    if as_of is None:
        as_of = date.today()
    results = apply_confidence(scored_current, results, as_of, config)

    if config.use_isolation_forest:
        from .iforest import flag_with_isolation_forest, reconcile_flags

        baseline_scored, _ = score_current(
            cleaned.loc[cleaned["season_id"].astype(str).isin(baseline_ids)],
            baseline,
            config,
        )
        baseline_scored = baseline_scored.merge(
            rain_by_date,
            on=["season_id", "date"],
            how="left",
            validate="many_to_one",
        )
        iforest_current, _ = flag_with_isolation_forest(
            baseline_scored, scored_current, config
        )
        results = reconcile_flags(results, iforest_current)
    results = apply_confidence(scored_current, results, as_of, config)
    results = add_rain_context(results, rain_features, config)
    results = rank_results(results, pd.DataFrame(fields), config)

    scored_full = cleaned.copy()
    current_key_mask = scored_full["season_id"].astype(str) == current_season
    current_keys = scored_full.loc[current_key_mask, ["field_id", "season_id", "date"]]
    scores = scored_current.set_index(["field_id", "season_id", "date"])
    for column in (
        "baseline_median",
        "baseline_sigma",
        "baseline_years",
        "z",
        "pct_dev",
        "cluster",
    ):
        scored_full.loc[current_key_mask, column] = [
            scores.loc[tuple(row), column]
            if tuple(row) in scores.index
            else None
            for row in current_keys.itertuples(index=False, name=None)
        ]
    scored_full["is_synthetic"] = synthetic
    for result in results:
        result.update(
            region_id=region_id,
            season_id=current_season,
            run_id=run_id,
            is_synthetic=synthetic,
        )
        result.pop("run_length", None)
        result.pop("baseline_median", None)
        result.pop("baseline_sigma", None)
    if output_dir is None:
        output_dir = data_dir.parent / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    scored_full.to_csv(output_dir / "observations.csv", index=False)
    rain_features.to_csv(output_dir / "rainfall.csv", index=False)
    result_frame = pd.DataFrame(results)
    for column in ("top_factors", "evidence"):
        if column in result_frame:
            result_frame[column] = result_frame[column].map(
                lambda value: json.dumps(value) if isinstance(value, (dict, list)) else value
            )
    result_frame.to_csv(output_dir / "field_results.csv", index=False)
    with (output_dir / "fields.geojson").open("w", encoding="utf-8") as target:
        json.dump(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": field["geometry"],
                        "properties": {
                            key: value
                            for key, value in field.items()
                            if key != "geometry"
                        },
                    }
                    for field in fields
                ],
                "region": region,
            },
            target,
        )
    report = None if skip_validation else validate_pipeline(cleaned, baseline_ids, config)
    if report is not None:
        report = {"run_id": run_id, **report}
        with (output_dir / "validation_report.json").open("w", encoding="utf-8") as target:
            json.dump(report, target, default=str, indent=2)
    run = {
        "run_id": run_id,
        "created_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "region_id": region_id,
        "season_id": current_season,
        "model_version": None,
        "model_checksum": None,
        "params": config_parameters(config),
        "is_synthetic": synthetic,
        "n_fields": len(fields),
        "notes": (
            "SYNTHETIC input; results are not Earth Engine or field measurements."
            if synthetic
            else "Offline pipeline run."
        ),
        "as_of": as_of.isoformat(),
    }
    with (output_dir / "analysis_run.json").open("w", encoding="utf-8") as target:
        json.dump(run, target, indent=2)
    return {
        "run": run,
        "regions": [region],
        "fields": fields,
        "observations": scored_full,
        "rainfall": rain_features,
        "field_results": results,
        "validation_report": report,
        "output_dir": output_dir,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--run-id", default=uuid.uuid4().hex)
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--load-to-mongo", action="store_true")
    args = parser.parse_args()
    result = run_pipeline(
        args.data_dir,
        args.region,
        args.run_id,
        args.skip_validation,
        as_of=args.as_of,
        output_dir=args.output_dir,
    )
    if args.load_to_mongo:
        from .load_to_mongo import load_processed_run

        load_processed_run(
            result["output_dir"],
            os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
            os.getenv("MONGODB_DB", "cropshield"),
        )
    counts = pd.Series(row["risk"] for row in result["field_results"]).value_counts().to_dict()
    print(f"run_id={args.run_id}; fields={len(result['fields'])}; risk_counts={counts}")


if __name__ == "__main__":
    main()
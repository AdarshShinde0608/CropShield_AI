from datetime import date
from math import isclose, isfinite
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.config import (
    BASELINE_START_YEAR,
    BASELINE_SEASON_COUNT,
    CURRENT_SEASON_START_YEAR,
    FIELD_COUNT,
    FIELD_SIDE_METERS,
    FIELD_ID_PAD_WIDTH,
    MINIMUM_ASSESSABLE_OBSERVATIONS,
    REGION_ID,
    SEED_RUN_ID,
    STRESS_FIELD_COUNT,
)
from pipeline.seed_demo import build_seed_data


def test_seed_dataset_has_the_expected_shape_and_risk_mix() -> None:
    data = build_seed_data()

    assert len(data["regions"]) == 1
    assert data["regions"][0]["name"] == "Demo Region (synthetic)"
    assert len(data["fields"]) == FIELD_COUNT == 40
    assert all(field["region_id"] == REGION_ID for field in data["fields"])
    assert all(field["is_synthetic_boundary"] is True for field in data["fields"])

    results = data["field_results"]
    assert len(results) == FIELD_COUNT
    by_field = {result["field_id"]: result for result in results}
    assert all(
        by_field[f"demo-field-{index + 1:0{FIELD_ID_PAD_WIDTH}d}"]["risk"]
        in {"alert", "watch"}
        for index in range(STRESS_FIELD_COUNT)
    )
    assert all(result["risk"] == "cannot_assess" for result in results[-3:])
    assert all(result["is_synthetic"] is True for result in results)
    assert all("placeholder_rule" not in result for result in results)
    assert all(result["severity"] is None or result["risk"] == "alert" for result in results)

    for result in results[-3:]:
        assert result["risk"] == "cannot_assess"
        assert result["n_valid_obs"] < MINIMUM_ASSESSABLE_OBSERVATIONS

    run = data["analysis_runs"][0]
    assert run["run_id"] == SEED_RUN_ID
    assert run["model_version"] is None
    assert run["model_checksum"] is None
    assert run["is_synthetic"] is True
    assert run["params"]["is_synthetic"] is True
    assert run["params"]["index"] == "NDVI"
    assert data["validation_reports"] == []


def test_seed_has_baseline_and_current_season_observations() -> None:
    data = build_seed_data()
    expected_seasons = {
        f"{year}-{str(year + 1)[-2:]}"
        for year in range(BASELINE_START_YEAR, BASELINE_START_YEAR + BASELINE_SEASON_COUNT)
    }
    expected_seasons.add(
        f"{CURRENT_SEASON_START_YEAR}-{str(CURRENT_SEASON_START_YEAR + 1)[-2:]}"
    )

    assert {season["season_id"] for season in data["seasons"]} == expected_seasons
    assert sum(season["role"] == "current" for season in data["seasons"]) == 1
    current_season_id = (
        f"{CURRENT_SEASON_START_YEAR}-{str(CURRENT_SEASON_START_YEAR + 1)[-2:]}"
    )
    assert {row["season_id"] for row in data["observations"]} == {current_season_id}
    assert len(data["observations"]) == FIELD_COUNT * len(
        {row["date"] for row in data["observations"]}
    )
    assert all(observation["is_synthetic"] is True for observation in data["observations"])
    assert any(row["baseline_median"] is not None for row in data["observations"])
    assert all(
        {"baseline_median", "baseline_sigma", "z", "pct_dev"}.issubset(row)
        for row in data["observations"]
    )

    current = [
        observation
        for observation in data["observations"]
        if observation["season_id"] == "2025-26"
    ]
    assert any(observation["ndvi"] is None for observation in current)
    assert any(observation["ndvi"] is not None for observation in current)
    assert all(0 <= observation["valid_frac"] <= 1 for observation in current)
    assert all(
        result["model_version"] is None
        and result["model_score"] is None
        and result["top_factors"] is None
        and result["decision_threshold"] is None
        for result in data["field_results"]
    )
    assert any(result["evidence"] for result in data["field_results"])


def test_geojson_polygons_are_closed_and_about_200_meters_per_side() -> None:
    data = build_seed_data()
    polygon = data["fields"][0]["geometry"]
    ring = polygon["coordinates"][0]
    assert polygon["type"] == "Polygon"
    assert ring[0] == ring[-1]
    latitude_side_m = (ring[2][1] - ring[1][1]) * 111_320
    assert isclose(latitude_side_m, FIELD_SIDE_METERS, rel_tol=0.02)


def test_rainfall_contains_one_synthetic_dry_spell_without_nan_values() -> None:
    data = build_seed_data()
    rainfall = data["rainfall"]
    assert rainfall
    assert {row["season_id"] for row in rainfall} == {"2025-26"}
    assert all(row["is_synthetic"] is True for row in rainfall)
    assert len({row["date"] for row in rainfall}) == len(rainfall)
    assert all(
        value is None or isfinite(value)
        for row in rainfall
        for value in (row["rain_mm"], row["rain14"], row["rain30"], row["rain_z"])
    )

    low_rain_days = [
        date.fromisoformat(row["date"])
        for row in rainfall
        if row["rain_mm"] < 0.5
    ]
    assert low_rain_days
    assert len(low_rain_days) < len(rainfall)

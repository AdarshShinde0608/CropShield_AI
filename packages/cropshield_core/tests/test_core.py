from dataclasses import replace
from datetime import date, timedelta
from math import nan

import pytest

from packages.cropshield_core import (
    PIPELINE_CONFIG,
    assess_data_quality,
    build_baseline_evidence,
    build_crop_type_features,
    day_of_season,
    rain_context_from_z,
    season_bounds,
)
from pipeline.config import PipelineConfig as PipelineCompatibilityConfig


def _clear_observation(observed_date: date, *, ndvi: float = 0.5) -> dict[str, object]:
    return {
        "date": observed_date.isoformat(),
        "ndvi": ndvi,
        "valid_frac": 0.9,
        "low_quality": False,
        "is_interpolated": False,
    }


def _model_row() -> dict[str, object]:
    return {
        "NDVI": 0.5,
        "NDWI": 0.1,
        "EVI": 0.3,
        "GNDVI": 0.2,
        "SAVI": 0.4,
        "Red": 0.2,
        "Green": 0.3,
        "Blue": 0.1,
        "NIR": 0.6,
        "SWIR": 0.25,
        "Season": "Rabi",
    }


def test_pipeline_config_is_reexported_and_calendar_helpers_are_stable() -> None:
    start, end = season_bounds("2025-26")

    assert isinstance(PIPELINE_CONFIG, PipelineCompatibilityConfig)
    assert (start, end) == (date(2025, 11, 1), date(2026, 3, 31))
    assert day_of_season(start, start) == 1
    assert day_of_season(start + timedelta(days=4), start) == 5


@pytest.mark.parametrize("label", ["2025", "2025-27", "bad-season"])
def test_season_bounds_rejects_invalid_labels(label: str) -> None:
    with pytest.raises(ValueError):
        season_bounds(label)


def test_feature_builder_returns_audited_columns_and_derived_values() -> None:
    features = build_crop_type_features(_model_row())

    assert tuple(features) == (
        "NDVI",
        "NDWI",
        "EVI",
        "GNDVI",
        "SAVI",
        "Red",
        "Green",
        "Blue",
        "NIR",
        "SWIR",
        "NIR_Red_ratio",
        "NDMI",
        "Red_NIR_diff",
        "is_kharif",
    )
    assert features["NIR_Red_ratio"] == pytest.approx(0.6 / 0.200001)
    assert features["NDMI"] == pytest.approx(0.35 / 0.850001)
    assert features["Red_NIR_diff"] == pytest.approx(0.4)
    assert features["is_kharif"] == 0


def test_feature_builder_requires_complete_finite_inputs_and_never_fills_nan() -> None:
    missing = _model_row()
    del missing["SWIR"]
    with pytest.raises(ValueError, match="SWIR"):
        build_crop_type_features(missing)

    nonfinite = _model_row()
    nonfinite["NDVI"] = nan
    with pytest.raises(ValueError, match="finite"):
        build_crop_type_features(nonfinite)


def test_feature_builder_matches_exact_kharif_category() -> None:
    row = _model_row()
    row["Season"] = "Kharif"

    assert build_crop_type_features(row)["is_kharif"] == 1


def test_quality_gate_requires_enough_clear_observations() -> None:
    today = date(2026, 2, 1)
    result = assess_data_quality(
        [_clear_observation(today - timedelta(days=1))],
        today,
    )

    assert result.risk == "cannot_assess"
    assert result.reason == "too_few_clear_observations"
    assert result.clear_observations == 1


def test_quality_gate_stale_boundary_and_clear_observation_filters() -> None:
    today = date(2026, 2, 1)
    stale_day = today - timedelta(days=PIPELINE_CONFIG.stale_days + 1)
    stale_rows = [
        _clear_observation(stale_day - timedelta(days=1)),
        _clear_observation(stale_day),
    ]
    stale = assess_data_quality(stale_rows, today)
    fresh_rows = [
        _clear_observation(today - timedelta(days=PIPELINE_CONFIG.stale_days)),
        _clear_observation(today - timedelta(days=1)),
    ]
    fresh_rows.extend(
        [
            {**_clear_observation(today), "is_interpolated": True},
            {**_clear_observation(today), "low_quality": True},
        ]
    )
    fresh = assess_data_quality(fresh_rows, today)

    assert stale.risk == "cannot_assess"
    assert stale.reason == "stale_observation"
    assert fresh.assessable
    assert fresh.risk is None
    assert fresh.clear_observations == 2


def test_quality_gate_does_not_count_nan_or_invalid_fractions_as_clear() -> None:
    today = date(2026, 2, 1)
    rows = [
        _clear_observation(today - timedelta(days=2), ndvi=nan),
        {**_clear_observation(today - timedelta(days=1)), "valid_frac": nan},
        {**_clear_observation(today), "valid_frac": 1.1},
    ]

    result = assess_data_quality(rows, today)

    assert result.risk == "cannot_assess"
    assert result.clear_observations == 0


def test_rain_context_handles_missing_nonfinite_and_threshold_edges() -> None:
    threshold = PIPELINE_CONFIG.rain_dry_z_threshold

    assert rain_context_from_z(None) == "not_applicable"
    assert rain_context_from_z(nan) == "not_applicable"
    assert rain_context_from_z(threshold) == "dry_spell"
    assert rain_context_from_z(threshold + 0.01) == "normal"
    assert rain_context_from_z(-0.5, replace(PIPELINE_CONFIG, rain_dry_z_threshold=-0.4)) == "dry_spell"


def test_baseline_evidence_matches_inclusive_dos_window_and_reports_band() -> None:
    baseline = [
        {
            "dos": 100,
            "baseline_median": 0.6,
            "baseline_lower": 0.4,
            "baseline_upper": 0.8,
        }
    ]
    rows = [
        {**_clear_observation(date(2026, 2, 1), ndvi=0.3), "dos": 112},
        {**_clear_observation(date(2026, 2, 2), ndvi=0.3), "dos": 112},
    ]

    result = build_baseline_evidence(rows, baseline)

    assert result["drop_start"] == date(2026, 2, 1)
    assert result["observations"][0]["baseline_median"] == 0.6
    assert result["observations"][0]["baseline_lower"] == 0.4
    assert result["observations"][0]["deviation_from_median"] == pytest.approx(-0.3)


def test_baseline_evidence_accepts_pipeline_sigma_and_matches_field() -> None:
    baseline = [
        {
            "field_id": "other-field",
            "dos": 100,
            "baseline_median": 0.8,
            "baseline_sigma": 0.05,
        },
        {
            "field_id": "field-1",
            "dos": 100,
            "baseline_median": 0.6,
            "baseline_sigma": 0.1,
        },
    ]
    observations = [
        {
            **_clear_observation(date(2026, 2, 1), ndvi=0.3),
            "field_id": "field-1",
            "dos": 100,
        },
        {
            **_clear_observation(date(2026, 2, 2), ndvi=0.3),
            "field_id": "field-1",
            "dos": 100,
        },
    ]

    result = build_baseline_evidence(observations, baseline)

    assert result["drop_start"] == date(2026, 2, 1)
    assert result["observations"][0]["baseline_median"] == 0.6
    assert result["observations"][0]["baseline_lower"] == pytest.approx(0.5)
    assert result["observations"][0]["baseline_upper"] == pytest.approx(0.7)


def test_baseline_evidence_rejects_dos_outside_window_and_breaks_on_cloud_gap() -> None:
    baseline = [
        {
            "dos": 100,
            "baseline_median": 0.6,
            "baseline_lower": 0.4,
            "baseline_upper": 0.8,
        }
    ]
    rows = [
        {**_clear_observation(date(2026, 2, 1), ndvi=0.3), "dos": 113},
        {
            **_clear_observation(date(2026, 2, 2), ndvi=0.3),
            "dos": 100,
            "low_quality": True,
        },
        {**_clear_observation(date(2026, 2, 3), ndvi=0.3), "dos": 100},
    ]

    result = build_baseline_evidence(rows, baseline)

    assert result["observations"][0]["baseline_median"] is None
    assert result["drop_start"] is None


def test_baseline_evidence_resets_on_large_date_gap_and_above_band_value() -> None:
    baseline = [
        {
            "dos": 100,
            "baseline_median": 0.6,
            "baseline_lower": 0.4,
            "baseline_upper": 0.8,
        }
    ]
    rows = [
        {**_clear_observation(date(2026, 2, 1), ndvi=0.3), "dos": 100},
        {
            **_clear_observation(
                date(2026, 2, 1) + timedelta(days=PIPELINE_CONFIG.max_interp_gap_days + 1),
                ndvi=0.3,
            ),
            "dos": 100,
        },
    ]

    result = build_baseline_evidence(rows, baseline)

    assert result["drop_start"] is None

    rows[-1] = {**_clear_observation(date(2026, 2, 2), ndvi=0.5), "dos": 100}
    above_band = build_baseline_evidence(rows, baseline)
    assert above_band["drop_start"] is None

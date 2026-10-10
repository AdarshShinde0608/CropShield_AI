from datetime import date, timedelta

import pandas as pd

from pipeline.confidence import assess_confidence
from pipeline.config import PIPELINE_CONFIG
from pipeline.context import add_rain_context, compute_rainfall_features


def _result(latest: date) -> dict[str, object]:
    return {
        "field_id": "field-1",
        "risk": "alert",
        "severity": "moderate",
        "confidence": 0.0,
        "confidence_label": "low",
        "latest_obs_date": latest,
        "baseline_years": 6,
        "baseline_median": 0.5,
        "baseline_sigma": 0.05,
        "run_length": 2,
        "if_agreement": False,
    }


def test_confidence_uses_weighted_evidence_and_stale_cutoff() -> None:
    today = date(2026, 2, 1)
    observations = pd.DataFrame(
        [
            {
                "date": today - timedelta(days=offset),
                "ndvi": 0.4,
                "valid_frac": 0.9,
                "low_quality": False,
                "is_interpolated": False,
                "z": -2.0,
            }
            for offset in range(3)
        ]
    )

    result = assess_confidence(observations, _result(today), today)
    stale = assess_confidence(
        observations,
        _result(today - timedelta(days=PIPELINE_CONFIG.stale_days + 1)),
        today,
    )

    assert result["confidence"] > PIPELINE_CONFIG.confidence_high_threshold
    assert result["confidence_label"] == "high"
    assert result["risk"] == "alert"
    assert stale["risk"] == "cannot_assess"
    assert stale["severity"] is None


def test_low_confidence_cannot_be_assessed() -> None:
    observations = pd.DataFrame(
        [
            {
                "date": date(2026, 2, 1),
                "ndvi": 0.4,
                "valid_frac": 0.1,
                "low_quality": True,
                "is_interpolated": False,
            }
        ]
    )
    result = assess_confidence(observations, _result(date(2026, 2, 1)), date(2026, 2, 1))

    assert result["risk"] == "cannot_assess"
    assert result["confidence_label"] == "low"


def test_rainfall_context_uses_baseline_window_and_safe_advice() -> None:
    rainfall_rows: list[dict[str, object]] = []
    for season_id, start, amount in (
        ("2023-24", date(2023, 11, 1), 2.0),
        ("2024-25", date(2024, 11, 1), 2.2),
        ("2025-26", date(2025, 11, 1), 0.1),
    ):
        for offset in range(30):
            rainfall_rows.append(
                {
                    "season_id": season_id,
                    "date": start + timedelta(days=offset),
                    "dos": offset + 1,
                    "rain_mm": amount,
                }
            )
    features = compute_rainfall_features(
        pd.DataFrame(rainfall_rows),
        ["2023-24", "2024-25"],
    )
    result = {
        "field_id": "field-1",
        "risk": "alert",
        "severity": "moderate",
        "drop_start": date(2025, 11, 30),
        "latest_obs_date": date(2025, 11, 30),
    }

    annotated = add_rain_context([result], features)[0]

    assert annotated["rain_context"] == "dry_spell"
    assert "inspect" in annotated["advice"].lower() or "check" in annotated["advice"].lower()
    assert "pest attack" not in annotated["advice"].lower()
    assert "drought confirmed" not in annotated["advice"].lower()


def test_empty_rainfall_remains_unavailable_instead_of_becoming_zero() -> None:
    features = compute_rainfall_features(
        pd.DataFrame(
            [{"season_id": "2025-26", "date": date(2025, 11, 1), "rain_mm": None}]
        ),
        ["2024-25"],
    )

    assert features.empty
    assert {"rain14", "rain30", "rain_z"}.issubset(features.columns)
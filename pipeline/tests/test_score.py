from datetime import date
from dataclasses import replace

import pandas as pd

from pipeline.config import PIPELINE_CONFIG
from pipeline.score import rank_results, score_current


def _baseline() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "field_id": "field-1",
                "dos": dos,
                "baseline_median": 0.5,
                "baseline_sigma": 0.05,
                "baseline_years": 6,
                "cluster": 0,
            }
            for dos in range(1, 200)
        ]
    )


def _observation(day: str, ndvi: float | None, **extra: object) -> dict[str, object]:
    return {
        "field_id": "field-1",
        "season_id": "2025-26",
        "date": day,
        "dos": (date.fromisoformat(day) - date(2025, 11, 1)).days + 1,
        "ndvi": ndvi,
        "valid_frac": 0.9,
        "low_quality": ndvi is None,
        "is_interpolated": False,
        **extra,
    }


def test_one_low_observation_is_watch_and_persistence_is_alert() -> None:
    frame = pd.DataFrame(
        [
            _observation("2025-11-01", 0.425),
            _observation("2025-11-11", 0.425),
        ]
    )
    _, results = score_current(frame, _baseline())

    assert results[0]["risk"] == "alert"
    assert results[0]["severity"] == "moderate"
    assert results[0]["drop_start"] == date(2025, 11, 1)
    assert results[0]["run_length"] == 2

    _, single = score_current(frame.iloc[:1], _baseline())
    assert single[0]["risk"] == "cannot_assess"

    one_observation_config = replace(
        PIPELINE_CONFIG,
        minimum_assessable_observations=1,
    )
    _, one_low = score_current(frame.iloc[:1], _baseline(), one_observation_config)
    assert one_low[0]["risk"] == "watch"


def test_two_strong_low_observations_produce_high_alert_severity() -> None:
    frame = pd.DataFrame(
        [
            _observation("2025-11-01", 0.4),
            _observation("2025-11-11", 0.4),
        ]
    )

    _, results = score_current(frame, _baseline())

    assert results[0]["risk"] == "alert"
    assert results[0]["severity"] == "high"


def test_cloudy_gap_breaks_low_run_and_resets_onset() -> None:
    frame = pd.DataFrame(
        [
            _observation("2025-11-01", 0.425),
            _observation("2025-11-11", 0.425),
            _observation("2025-11-21", None),
            _observation("2025-12-01", 0.425),
        ]
    )
    _, results = score_current(frame, _baseline())

    assert results[0]["risk"] == "watch"
    assert results[0]["drop_start"] == date(2025, 12, 1)
    assert results[0]["run_length"] == 1


def test_interpolated_observation_never_extends_or_triggers_low_run() -> None:
    frame = pd.DataFrame(
        [
            _observation("2025-11-01", 0.425),
            _observation("2025-11-06", 0.20, is_interpolated=True),
            _observation("2025-11-11", 0.425),
        ]
    )
    _, results = score_current(frame, _baseline())

    assert results[0]["risk"] == "cannot_assess"
    assert results[0]["drop_start"] is None


def test_rank_orders_alert_before_watch_and_is_stable() -> None:
    results = [
        {"field_id": "b", "risk": "watch", "confidence": 0.8, "z_score": -2.0, "run_length": 1},
        {"field_id": "a", "risk": "alert", "confidence": 0.5, "z_score": -1.6, "run_length": 2},
    ]

    ranked = rank_results(results, config=PIPELINE_CONFIG)

    assert [row["field_id"] for row in ranked] == ["a", "b"]
    assert [row["priority_rank"] for row in ranked] == [1, 2]
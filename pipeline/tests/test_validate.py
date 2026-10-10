from dataclasses import replace
from datetime import date, timedelta

import pandas as pd

from pipeline.config import PIPELINE_CONFIG
from pipeline.validate import _classification_metrics, validate_pipeline


def test_unobserved_metrics_are_null_instead_of_fabricated_zeros() -> None:
    metrics = _classification_metrics(0, 0, 0, 0)

    assert metrics["precision"] is None
    assert metrics["recall"] is None
    assert metrics["false_alarm_rate"] is None
    assert metrics["f1"] is None


def test_validation_reports_only_metrics_computed_from_the_fixture() -> None:
    rows = []
    for season_index, season in enumerate(("2023-24", "2024-25", "2025-26")):
        start = date(2023 + season_index, 11, 1)
        for field in ("field-1", "field-2"):
            for dos in (1, 15, 30, 45, 60):
                rows.append(
                    {
                        "field_id": field,
                        "season_id": season,
                        "date": start + timedelta(days=dos - 1),
                        "dos": dos,
                        "ndvi": 0.45 + dos / 600 + (0.01 if field == "field-2" else 0.0),
                        "valid_frac": 0.9,
                        "low_quality": False,
                        "is_interpolated": False,
                    }
                )
    config = replace(
        PIPELINE_CONFIG,
        baseline_seasons=("2023-24", "2024-25"),
        injection_magnitudes=(0.8,),
        threshold_sweep_watch_start=-1.5,
        threshold_sweep_watch_stop=-1.5,
        threshold_sweep_watch_step=-0.5,
        threshold_sweep_persistence_min=1,
        threshold_sweep_persistence_max=1,
    )

    report = validate_pipeline(pd.DataFrame(rows), ("2023-24", "2024-25"), config)

    assert report["loyo"]["fields_evaluated"] == 4
    assert report["injection"][0]["magnitude_multiplier"] == 0.8
    assert set(report["injection"][0]).issuperset(
        {"precision", "recall", "false_alarm_rate", "detection_delay_days", "f1"}
    )
    assert report["thresholds_sweep"][0]["fields_evaluated"] > 0
    assert (
        report["limitations"]
        == "Synthetic injection tests do not establish real-world detection accuracy."
    )

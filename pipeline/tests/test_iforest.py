from dataclasses import replace
from datetime import date, timedelta

import pandas as pd

from pipeline.config import PIPELINE_CONFIG
from pipeline.iforest import flag_with_isolation_forest, reconcile_flags


def test_iforest_is_baseline_trained_and_never_creates_an_alert_alone() -> None:
    baseline_rows = []
    for field_index in range(4):
        for offset in range(8):
            baseline_rows.append(
                {
                    "field_id": f"field-{field_index}",
                    "date": date(2024, 11, 1) + timedelta(days=offset * 5),
                    "ndvi": 0.4 + offset * 0.02 + field_index * 0.005,
                    "z": 0.1,
                    "rain_z": 0.0,
                    "valid_frac": 0.9,
                    "low_quality": False,
                    "is_interpolated": False,
                }
            )
    current_rows = [
        {
            "field_id": f"field-{field_index}",
            "date": date(2025, 11, 1),
            "ndvi": 0.2 if field_index == 0 else 0.55,
            "z": -1.8 if field_index == 0 else 0.2,
            "rain_z": -0.2,
            "valid_frac": 0.9,
            "low_quality": False,
            "is_interpolated": False,
        }
        for field_index in range(4)
    ]
    config = replace(
        PIPELINE_CONFIG,
        use_isolation_forest=True,
        iforest_estimators=20,
        iforest_contamination=0.25,
    )

    flagged, _ = flag_with_isolation_forest(
        pd.DataFrame(baseline_rows),
        pd.DataFrame(current_rows),
        config,
    )
    results = reconcile_flags(
        [
            {
                "field_id": "field-0",
                "risk": "normal",
                "severity": None,
                "confidence": 0.7,
            },
            {
                "field_id": "field-1",
                "risk": "cannot_assess",
                "severity": None,
                "confidence": 0.1,
            },
        ],
        flagged,
    )

    assert all(result["risk"] != "alert" for result in results)
    assert results[1]["risk"] == "cannot_assess"

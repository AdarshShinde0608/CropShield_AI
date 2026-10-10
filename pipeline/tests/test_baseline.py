from dataclasses import replace

import pandas as pd

from pipeline.baseline import build_baseline
from pipeline.config import PIPELINE_CONFIG


def _observations() -> pd.DataFrame:
    rows = []
    values = {
        "a": {"2019-20": 0.30, "2020-21": 0.31, "2021-22": 0.29, "2025-26": 0.95},
        "b": {"2019-20": 0.40, "2020-21": 0.41, "2021-22": 0.39},
        "c": {"2019-20": 0.42, "2020-21": 0.43, "2021-22": 0.41},
    }
    for field_id, seasons in values.items():
        for season_id, ndvi in seasons.items():
            if season_id == "2025-26":
                rows.append(
                    {
                        "field_id": field_id,
                        "season_id": season_id,
                        "dos": 80,
                        "ndvi": ndvi,
                        "low_quality": False,
                        "is_interpolated": False,
                    }
                )
                continue
            rows.extend(
                {
                    "field_id": field_id,
                    "season_id": season_id,
                    "dos": dos,
                    "ndvi": ndvi + offset,
                    "low_quality": False,
                    "is_interpolated": False,
                }
                for dos, offset in ((78, -0.01), (80, 0.0), (82, 0.01))
            )
    return pd.DataFrame(rows)


def test_baseline_never_uses_current_season() -> None:
    baseline, _ = build_baseline(
        _observations(),
        ["2019-20", "2020-21", "2021-22"],
        PIPELINE_CONFIG,
    )

    field_a = baseline.loc[(baseline["field_id"] == "a") & (baseline["dos"] == 80)].iloc[0]
    assert field_a["baseline_median"] < 0.5


def test_small_sample_falls_back_to_cluster_center_and_sigma_floor() -> None:
    observations = _observations()
    observations = observations.loc[
        ~(
            (observations["field_id"] == "a")
            & (observations["season_id"] != "2019-20")
        )
    ]
    config = replace(
        PIPELINE_CONFIG,
        baseline_cluster_min=4,
        baseline_cluster_max=4,
    )
    baseline, clusters = build_baseline(
        observations,
        ["2019-20", "2020-21", "2021-22"],
        config,
    )

    field_a = baseline.loc[(baseline["field_id"] == "a") & (baseline["dos"] == 80)].iloc[0]
    assert field_a["baseline_years"] == 1
    assert 0.35 < field_a["baseline_median"] < 0.45
    assert clusters["a"] == clusters["b"] == clusters["c"]
    assert (baseline["baseline_sigma"] >= config.sigma_floor).all()
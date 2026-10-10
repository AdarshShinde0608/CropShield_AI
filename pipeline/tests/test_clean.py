from datetime import date

import pandas as pd

from pipeline.clean import clean_observations, regularize_observations
from pipeline.config import PIPELINE_CONFIG


def _frame(rows: list[tuple[str, float | None]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "field_id": "field-1",
                "season_id": "2025-26",
                "date": day,
                "ndvi": value,
                "valid_frac": 0.9,
                "low_quality": False,
                "is_interpolated": False,
            }
            for day, value in rows
        ]
    )


def test_clean_drops_nan_and_isolated_spike_and_sets_dos() -> None:
    observations = _frame(
        [
            ("2025-11-01", 0.40),
            ("2025-11-06", 0.90),
            ("2025-11-11", 0.41),
            ("2025-11-16", None),
            ("2025-11-21", 0.42),
        ]
    )

    cleaned = clean_observations(observations)

    assert cleaned["date"].tolist() == [date(2025, 11, 1), date(2025, 11, 11), date(2025, 11, 21)]
    assert cleaned["dos"].tolist() == [1, 11, 21]


def test_regularization_marks_only_short_gap_interpolations() -> None:
    observations = _frame(
        [
            ("2025-11-01", 0.40),
            ("2025-11-11", 0.50),
            ("2025-11-21", 0.60),
            ("2025-12-21", 0.70),
        ]
    )
    cleaned = clean_observations(observations)

    regularized = regularize_observations(cleaned)
    inserted = regularized.loc[regularized["is_interpolated"]]

    assert inserted["date"].tolist() == [date(2025, 11, 6), date(2025, 11, 16)]
    assert not inserted.loc[inserted["date"] == date(2025, 11, 16), "ndvi"].empty
    assert date(2025, 12, 1) not in regularized["date"].tolist()


def test_low_valid_fraction_is_preserved_as_a_quality_flag() -> None:
    observations = _frame([("2025-11-01", 0.4)])
    observations.loc[0, "valid_frac"] = PIPELINE_CONFIG.min_valid_frac / 2

    cleaned = clean_observations(observations)

    assert len(cleaned) == 1
    assert bool(cleaned.iloc[0]["low_quality"]) is True
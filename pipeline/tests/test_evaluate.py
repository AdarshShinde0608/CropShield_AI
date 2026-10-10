import pandas as pd
import pytest

from pipeline.evaluate import evaluate_predictions


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "field_id": "a",
                "y_true": "normal",
                "y_pred": "normal",
                "is_synthetic": False,
                "cloud_gap": False,
                "missing_dates": False,
                "short_season": False,
                "baseline_pred": "watch",
                "prob_alert": 0.05,
                "prob_normal": 0.90,
                "prob_watch": 0.05,
                "latency_ms": 10.0,
            },
            {
                "field_id": "b",
                "y_true": "watch",
                "y_pred": "normal",
                "is_synthetic": False,
                "cloud_gap": True,
                "missing_dates": False,
                "short_season": True,
                "baseline_pred": "watch",
                "prob_alert": 0.05,
                "prob_normal": 0.60,
                "prob_watch": 0.35,
                "latency_ms": 30.0,
            },
        ]
    )


def test_evaluation_contains_provenance_metrics_robustness_baseline_calibration_latency() -> None:
    report = evaluate_predictions(
        _rows(), "documented-set-v1", "held-out-area-2025", "cropstress-v1"
    )

    primary = report["primary"]
    assert primary["provenance"]["dataset"] == "documented-set-v1"
    assert primary["provenance"]["split"] == "held-out-area-2025"
    assert primary["provenance"]["sample_count"] == 2
    assert primary["provenance"]["field_count"] == 2
    assert primary["confusion_matrix"] == [[1, 0], [1, 0]]
    assert primary["per_class"]["normal"]["precision"] == 0.5
    assert primary["per_class"]["watch"]["recall"] == 0.0
    assert report["robustness"]["cloud_gap"]["status"] == "evaluated"
    assert report["robustness"]["cloud_gap"]["provenance"]["sample_count"] == 1
    assert report["robustness"]["missing_dates"]["status"] == "not_evaluated"
    assert report["baseline_comparison"]["method"] == "NDVI z-score baseline comparison"
    assert report["calibration"]["provenance"]["dataset"] == "documented-set-v1"
    assert report["latency"]["provenance"]["field_count"] == 2
    assert report["latency"]["mean"] == 20.0


def test_evaluation_marks_unsupplied_robustness_checks_not_evaluated() -> None:
    rows = _rows().drop(columns=["cloud_gap", "missing_dates", "short_season"])

    report = evaluate_predictions(rows, "dataset", "split", "model-v1")

    assert all(
        report["robustness"][name]["status"] == "not_evaluated"
        for name in ("cloud_gap", "missing_dates", "short_season")
    )


def test_evaluation_rejects_missing_provenance_columns_and_mixed_synthetic_rows() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        evaluate_predictions(
            _rows().drop(columns=["is_synthetic"]), "dataset", "split", "model-v1"
        )

    rows = _rows()
    rows.loc[1, "is_synthetic"] = True
    with pytest.raises(ValueError, match="mix synthetic"):
        evaluate_predictions(rows, "dataset", "split", "model-v1")


def test_evaluation_rejects_invalid_probability_and_latency_values() -> None:
    rows = _rows()
    rows.loc[0, "prob_normal"] = 1.2
    rows.loc[0, "prob_watch"] = -0.25
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        evaluate_predictions(rows, "dataset", "split", "model-v1")

    rows = _rows()
    rows.loc[0, "latency_ms"] = -1
    with pytest.raises(ValueError, match="latency_ms"):
        evaluate_predictions(rows, "dataset", "split", "model-v1")


def test_evaluation_rejects_probability_argmax_mismatch() -> None:
    rows = _rows()
    rows.loc[0, "prob_normal"] = 0.05
    rows.loc[0, "prob_watch"] = 0.9

    with pytest.raises(ValueError, match="argmax"):
        evaluate_predictions(rows, "dataset", "split", "model-v1")

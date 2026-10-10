"""Evaluate saved held-out predictions without training or loading model files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from packages.cropshield_core.config import PIPELINE_CONFIG

_REQUIRED_COLUMNS = {"field_id", "y_true", "y_pred", "is_synthetic"}
_ROBUSTNESS_FLAGS = ("cloud_gap", "missing_dates", "short_season")


def _truthy(value: object, column: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalised = value.strip().lower()
        if normalised in {"true", "1", "yes"}:
            return True
        if normalised in {"false", "0", "no"}:
            return False
    raise ValueError(f"{column} values must be booleans or 0/1")


def _metric_provenance(
    dataset: str,
    split: str,
    frame: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "split": split,
        "sample_count": int(len(frame)),
        "field_count": int(frame["field_id"].nunique()),
        "synthetic": bool(frame["is_synthetic"].iloc[0]),
        "class_counts": {
            str(name): int(count)
            for name, count in frame["y_true"].value_counts().sort_index().items()
        },
    }


def _classification_summary(
    frame: pd.DataFrame,
    dataset: str,
    split: str,
) -> dict[str, Any]:
    if frame.empty:
        raise ValueError("cannot compute classification metrics for zero rows")
    labels = sorted(set(frame["y_true"].astype(str)) | set(frame["y_pred"].astype(str)))
    truth = frame["y_true"].astype(str)
    predicted = frame["y_pred"].astype(str)
    matrix = [
        [
            int(((truth == actual) & (predicted == guess)).sum())
            for guess in labels
        ]
        for actual in labels
    ]
    per_class: dict[str, dict[str, Any]] = {}
    for index, label in enumerate(labels):
        true_positive = matrix[index][index]
        false_positive = sum(matrix[actual][index] for actual in range(len(labels)) if actual != index)
        false_negative = sum(matrix[index][guess] for guess in range(len(labels)) if guess != index)
        support = sum(matrix[index])
        precision_denominator = true_positive + false_positive
        recall_denominator = true_positive + false_negative
        precision = true_positive / precision_denominator if precision_denominator else None
        recall = true_positive / recall_denominator if recall_denominator else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall > 0
            else 0.0
            if precision is not None and recall is not None
            else None
        )
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    return {
        "provenance": _metric_provenance(dataset, split, frame),
        "labels": labels,
        "confusion_matrix": matrix,
        "per_class": per_class,
    }


def _expected_calibration_error(
    frame: pd.DataFrame,
    probability_columns: list[str],
) -> float:
    labels = [column.removeprefix("prob_") for column in probability_columns]
    probabilities = frame[probability_columns].to_numpy(dtype=float)
    if not np.isfinite(probabilities).all():
        raise ValueError("probability values must all be finite")
    if ((probabilities < 0.0) | (probabilities > 1.0)).any():
        raise ValueError("probabilities must be in [0, 1]")
    if not np.allclose(probabilities.sum(axis=1), 1.0, rtol=1e-5, atol=1e-6):
        raise ValueError("each probability row must sum to 1")
    predicted_indices = probabilities.argmax(axis=1)
    predicted_labels = np.asarray(labels)[predicted_indices]
    if not np.array_equal(predicted_labels, frame["y_pred"].astype(str).to_numpy()):
        raise ValueError("y_pred must match the argmax class in the probability columns")
    confidence = probabilities.max(axis=1)
    correct = (predicted_labels == frame["y_true"].astype(str).to_numpy()).astype(float)
    bins = PIPELINE_CONFIG.evaluation_calibration_bins
    edges = np.linspace(0.0, 1.0, bins + 1)
    error = 0.0
    for index in range(bins):
        mask = (confidence >= edges[index]) & (
            confidence <= edges[index + 1]
            if index == bins - 1
            else confidence < edges[index + 1]
        )
        if mask.any():
            error += float(mask.mean()) * abs(float(correct[mask].mean()) - float(confidence[mask].mean()))
    return error


def evaluate_predictions(
    predictions: pd.DataFrame,
    dataset: str,
    split: str,
    model_version: str,
) -> dict[str, Any]:
    """Compute metrics from held-out prediction rows and declared provenance.

    The input CSV must contain actual, paired labels and predictions. It must
    also explicitly mark whether rows are synthetic, and may contain boolean
    robustness flags, a ``baseline_pred`` comparison, model probabilities
    named ``prob_<class>``, and measured ``latency_ms`` values.
    """
    missing = _REQUIRED_COLUMNS - set(predictions.columns)
    if missing:
        raise ValueError(f"prediction file missing columns: {', '.join(sorted(missing))}")
    if not dataset.strip() or not split.strip() or not model_version.strip():
        raise ValueError("dataset, split, and model version descriptions are required")
    frame = predictions.copy()
    if frame[["field_id", "y_true", "y_pred"]].isna().any().any():
        raise ValueError("field_id, y_true, and y_pred cannot contain missing values")
    synthetic_flags = frame["is_synthetic"].map(lambda value: _truthy(value, "is_synthetic"))
    if synthetic_flags.nunique() != 1:
        raise ValueError("a prediction report cannot mix synthetic and non-synthetic rows")
    frame["is_synthetic"] = synthetic_flags
    frame["field_id"] = frame["field_id"].astype(str)
    frame["y_true"] = frame["y_true"].astype(str)
    frame["y_pred"] = frame["y_pred"].astype(str)

    report: dict[str, Any] = {
        "evaluation_status": "complete",
        "evaluation_type": "held_out",
        "generated_by": "pipeline.evaluate",
        "model_version": model_version,
        "primary": _classification_summary(frame, dataset, split),
        "robustness": {},
        "baseline_comparison": None,
        "calibration": None,
        "latency": None,
    }

    for flag in _ROBUSTNESS_FLAGS:
        if flag not in frame:
            report["robustness"][flag] = {
                "status": "not_evaluated",
                "reason": f"{flag} labels were not supplied",
            }
            continue
        mask = frame[flag].map(lambda value: _truthy(value, flag))
        subset = frame.loc[mask]
        report["robustness"][flag] = (
            {
                "status": "evaluated",
                **_classification_summary(subset, dataset, f"{split}; {flag}=true"),
            }
            if not subset.empty
            else {
                "status": "not_evaluated",
                "reason": f"no rows marked {flag}=true",
            }
        )

    if "baseline_pred" in frame:
        if frame["baseline_pred"].isna().any():
            raise ValueError("baseline_pred cannot contain missing values")
        comparison = frame.rename(columns={"y_pred": "model_pred", "baseline_pred": "y_pred"})
        report["baseline_comparison"] = {
            "method": "NDVI z-score baseline comparison",
            **_classification_summary(comparison, dataset, split),
        }

    probability_columns = sorted(
        column for column in frame if column.startswith("prob_")
    )
    if probability_columns:
        probability_labels = {column.removeprefix("prob_") for column in probability_columns}
        expected_labels = set(frame["y_true"]) | set(frame["y_pred"])
        if not expected_labels.issubset(probability_labels):
            raise ValueError("probability columns must cover all true and predicted classes")
        report["calibration"] = {
            "method": "top-label expected calibration error",
            "bin_count": PIPELINE_CONFIG.evaluation_calibration_bins,
            "value": _expected_calibration_error(frame, probability_columns),
            "provenance": _metric_provenance(dataset, split, frame),
        }

    if "latency_ms" in frame:
        latency = pd.to_numeric(frame["latency_ms"], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(latency).all() or (latency < 0.0).any():
            raise ValueError("latency_ms must contain finite, non-negative measurements")
        per_field = pd.DataFrame({"field_id": frame["field_id"], "latency_ms": latency})
        field_latency = per_field.groupby("field_id")["latency_ms"].mean()
        report["latency"] = {
            "unit": "milliseconds per field",
            "mean": float(field_latency.mean()),
            "median": float(field_latency.median()),
            "p95": float(np.percentile(field_latency.to_numpy(), 95)),
            "provenance": _metric_provenance(dataset, split, frame),
        }
    return report


def evaluate_file(
    predictions_path: Path,
    output_path: Path,
    dataset: str,
    split: str,
    model_version: str,
) -> dict[str, Any]:
    """Evaluate a CSV of saved predictions and write a JSON report."""
    predictions = pd.read_csv(predictions_path)
    report = evaluate_predictions(predictions, dataset, split, model_version)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True, help="CSV containing held-out model predictions")
    parser.add_argument("--dataset", required=True, help="Exact dataset name/version used for evaluation")
    parser.add_argument("--split", required=True, help="Exact held-out split description")
    parser.add_argument("--model-version", required=True, help="Exact model version that produced these predictions")
    parser.add_argument("--out", type=Path, required=True, help="Destination evaluation JSON")
    args = parser.parse_args()
    evaluate_file(args.predictions, args.out, args.dataset, args.split, args.model_version)


if __name__ == "__main__":
    main()

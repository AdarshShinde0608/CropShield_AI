"""Measured temporal backtesting and explicitly synthetic anomaly injection."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd

from .baseline import build_baseline
from .config import PIPELINE_CONFIG, PipelineConfig
from .score import score_current


def _alert_count(results: list[dict[str, Any]]) -> int:
    return sum(result["risk"] in {"watch", "alert"} for result in results)


def _per_class_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        risk: sum(result["risk"] == risk for result in results)
        for risk in ("normal", "watch", "alert", "cannot_assess")
    }


def _baseline_and_score(
    data: pd.DataFrame,
    held_out_season: str,
    baseline_ids: list[str],
    config: PipelineConfig,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    reference = data.loc[data["season_id"].astype(str).isin(baseline_ids)]
    held_out = data.loc[data["season_id"].astype(str) == held_out_season].copy()
    baseline, _ = build_baseline(reference, baseline_ids, config)
    _, results = score_current(held_out, baseline, config)
    return held_out, results


def _classification_metrics(
    true_positive: int,
    false_positive: int,
    false_negative: int,
    true_negative: int,
) -> dict[str, float | int | None]:
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    far_denominator = false_positive + true_negative
    precision = (
        true_positive / precision_denominator if precision_denominator else None
    )
    recall = true_positive / recall_denominator if recall_denominator else None
    false_alarm_rate = false_positive / far_denominator if far_denominator else None
    f1: float | None = None
    if precision is not None and recall is not None:
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
    return {
        "precision": precision,
        "recall": recall,
        "false_alarm_rate": false_alarm_rate,
        "f1": f1,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
    }


def validate_pipeline(
    observations: pd.DataFrame,
    baseline_season_ids: list[str] | tuple[str, ...],
    config: PipelineConfig = PIPELINE_CONFIG,
) -> dict[str, Any]:
    """Run leave-one-year-out, injected-stress, fixed-threshold, and sweep tests."""
    required = {"field_id", "season_id", "date", "dos", "ndvi", "valid_frac"}
    if not required.issubset(observations.columns):
        raise ValueError(f"observations must include {sorted(required)}")
    baseline_ids = sorted({str(value) for value in baseline_season_ids})
    loyo_rows: list[dict[str, Any]] = []
    false_alerts = 0
    evaluated_fields = 0
    all_class_counts = {name: 0 for name in ("normal", "watch", "alert", "cannot_assess")}
    for held_out in baseline_ids:
        training_ids = [season for season in baseline_ids if season != held_out]
        if not training_ids:
            continue
        _, results = _baseline_and_score(observations, held_out, training_ids, config)
        count = len(results)
        alerted = _alert_count(results)
        false_alerts += alerted
        evaluated_fields += count
        class_counts = _per_class_counts(results)
        for risk, risk_count in class_counts.items():
            all_class_counts[risk] += risk_count
        loyo_rows.append(
            {
                "season_id": held_out,
                "fields_evaluated": count,
                "false_alerts": alerted,
                "false_alert_rate": alerted / count if count else None,
                "class_counts": class_counts,
            }
        )
    loyo_report = {
        "false_alert_rate_per_field_season": (
            false_alerts / evaluated_fields if evaluated_fields else None
        ),
        "fields_evaluated": evaluated_fields,
        "false_alerts": false_alerts,
        "per_class_counts": all_class_counts,
        "by_season": loyo_rows,
    }

    rng = np.random.default_rng(config.random_state)
    injection_reports: list[dict[str, Any]] = []
    fixed_baseline_reports: list[dict[str, Any]] = []
    for magnitude in config.injection_magnitudes:
        tp = fp = fn = tn = 0
        detection_delays: list[float] = []
        fixed_tp = fixed_fp = fixed_fn = fixed_tn = 0
        for held_out in baseline_ids:
            training_ids = [season for season in baseline_ids if season != held_out]
            if not training_ids:
                continue
            original, control_results = _baseline_and_score(
                observations, held_out, training_ids, config
            )
            controls = original.loc[
                original["ndvi"].notna()
                & original["valid_frac"].ge(config.min_valid_frac)
            ]
            field_ids = sorted(controls["field_id"].astype(str).unique())
            fp += _alert_count(control_results)
            tn += max(0, len(field_ids) - _alert_count(control_results))
            fixed_control = controls.groupby("field_id")["ndvi"].min()
            fixed_fp += int((fixed_control < config.fixed_ndvi_threshold).sum())
            fixed_tn += max(0, len(fixed_control) - int((fixed_control < config.fixed_ndvi_threshold).sum()))

            injected = original.copy(deep=True)
            injected["field_id"] = injected["field_id"].astype(str)
            start_dates: dict[str, Any] = {}
            for field_id in field_ids:
                indices = injected.index[injected["field_id"] == field_id].tolist()
                indices.sort(key=lambda index: injected.at[index, "date"])
                start_index = min(
                    int(len(indices) * config.injection_min_start_fraction),
                    max(0, len(indices) - config.persistence_alert_count),
                )
                if len(indices) < config.persistence_alert_count:
                    continue
                start_idx = int(rng.integers(start_index, len(indices) - config.persistence_alert_count + 1))
                chosen_index = indices[start_idx]
                start_dates[field_id] = injected.at[chosen_index, "date"]
                later_indices = [
                    index for index in indices if injected.at[index, "date"] >= start_dates[field_id]
                ]
                injected.loc[later_indices, "ndvi"] = (
                    pd.to_numeric(injected.loc[later_indices, "ndvi"], errors="coerce")
                    * float(magnitude)
                )
            _, injected_results = score_current(injected, build_baseline(
                observations.loc[observations["season_id"].astype(str).isin(training_ids)],
                training_ids,
                config,
            )[0], config)
            injected_by_id = {row["field_id"]: row for row in injected_results}
            for field_id in field_ids:
                if field_id not in start_dates:
                    continue
                onset = injected_by_id[field_id].get("drop_start")
                detected = (
                    injected_by_id[field_id]["risk"] in {"watch", "alert"}
                    and onset is not None
                    and pd.Timestamp(onset) >= pd.Timestamp(start_dates[field_id])
                )
                tp += int(detected)
                fn += int(not detected)
                if detected:
                    delay = (pd.Timestamp(onset) - pd.Timestamp(start_dates[field_id])).days
                    detection_delays.append(float(delay))
                fixed_detected = bool(
                    (pd.to_numeric(injected.loc[
                        (injected["field_id"] == field_id)
                        & (injected["date"] >= start_dates[field_id]),
                        "ndvi",
                    ], errors="coerce") < config.fixed_ndvi_threshold).any()
                )
                fixed_tp += int(fixed_detected)
                fixed_fn += int(not fixed_detected)
        metrics = _classification_metrics(tp, fp, fn, tn)
        metrics["detection_delay_days"] = (
            float(np.mean(detection_delays)) if detection_delays else None
        )
        injection_reports.append({"magnitude_multiplier": magnitude, **metrics})
        fixed_metrics = _classification_metrics(fixed_tp, fixed_fp, fixed_fn, fixed_tn)
        fixed_metrics["detection_delay_days"] = None
        fixed_baseline_reports.append(
            {"magnitude_multiplier": magnitude, **fixed_metrics}
        )

    watch_values = np.arange(
        config.threshold_sweep_watch_start,
        config.threshold_sweep_watch_stop + config.threshold_sweep_watch_step / 2,
        config.threshold_sweep_watch_step,
    )
    sweep: list[dict[str, Any]] = []
    for threshold in watch_values:
        for persistence in range(
            config.threshold_sweep_persistence_min,
            config.threshold_sweep_persistence_max + 1,
        ):
            candidate = replace(
                config,
                z_watch=float(threshold),
                persistence_alert_count=persistence,
            )
            field_count = alert_count = 0
            for held_out in baseline_ids:
                training_ids = [season for season in baseline_ids if season != held_out]
                if not training_ids:
                    continue
                _, results = _baseline_and_score(
                    observations, held_out, training_ids, candidate
                )
                field_count += len(results)
                alert_count += _alert_count(results)
            sweep.append(
                {
                    "z_watch": float(threshold),
                    "persistence": persistence,
                    "fields_evaluated": field_count,
                    "false_alerts": alert_count,
                    "false_alert_rate": alert_count / field_count if field_count else None,
                }
            )
    return {
        "loyo": loyo_report,
        "injection": injection_reports,
        "baseline_comparison": {
            "method": "fixed_ndvi_threshold",
            "threshold": config.fixed_ndvi_threshold,
            "metrics_by_magnitude": fixed_baseline_reports,
        },
        "thresholds_sweep": sweep,
        "limitations": (
            "Synthetic injection tests do not establish real-world detection accuracy."
        ),
    }
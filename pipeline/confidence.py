"""Quality-weighted confidence and stale-observation assessability."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from .config import PIPELINE_CONFIG, PipelineConfig


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def assess_confidence(
    observations: pd.DataFrame,
    result: dict[str, Any],
    as_of: date | None = None,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> dict[str, Any]:
    """Return weighted confidence, label, and effective risk for one field."""
    if as_of is None:
        as_of = date.today()
    field_rows = observations.copy()
    field_rows["date"] = field_rows["date"].map(_as_date)
    if "valid_frac" not in field_rows:
        field_rows["valid_frac"] = np.nan
    clear_mask = (
        field_rows.get("ndvi", pd.Series(index=field_rows.index, dtype=float)).notna()
        & pd.to_numeric(field_rows["valid_frac"], errors="coerce").ge(config.min_valid_frac)
        & ~field_rows.get(
            "low_quality", pd.Series(False, index=field_rows.index)
        ).fillna(True).astype(bool)
        & ~field_rows.get(
            "is_interpolated", pd.Series(False, index=field_rows.index)
        ).fillna(False).astype(bool)
    )
    clear = field_rows.loc[clear_mask].sort_values("date", kind="stable")
    recent = clear.tail(config.recent_observation_count)
    valid_component = (
        float(pd.to_numeric(recent["valid_frac"], errors="coerce").mean())
        if not recent.empty
        else 0.0
    )
    persistence_component = min(
        float(result.get("run_length") or 0) / config.persistence_alert_count,
        1.0,
    )
    baseline_component = min(
        float(result.get("baseline_years") or 0) / config.min_baseline_years,
        1.0,
    )
    center = result.get("baseline_median")
    sigma = result.get("baseline_sigma")
    if center is None or sigma is None or float(center) <= 0:
        stability_component = 0.0
    else:
        stability_component = max(0.0, 1.0 - min(float(sigma) / float(center), 1.0))
    z_values = pd.to_numeric(clear.get("z", pd.Series(dtype=float)), errors="coerce").dropna()
    vci_values = pd.to_numeric(clear.get("vci", pd.Series(dtype=float)), errors="coerce").dropna()
    if not z_values.empty and not vci_values.empty:
        agreement_component = float((np.sign(z_values.tail(1).iloc[0]) == np.sign(vci_values.tail(1).iloc[0])).item())
    else:
        agreement_component = 0.5
    weights = (
        (config.confidence_valid_frac_weight, valid_component),
        (config.confidence_persistence_weight, persistence_component),
        (config.confidence_baseline_years_weight, baseline_component),
        (config.confidence_baseline_stability_weight, stability_component),
        (config.confidence_signal_agreement_weight, agreement_component),
    )
    confidence = sum(weight * component for weight, component in weights)
    if clear.empty:
        confidence = 0.0
    if result.get("if_agreement"):
        confidence += config.confidence_isolation_forest_bonus
    confidence = min(max(confidence, 0.0), 1.0)
    confidence_label = (
        "high"
        if confidence >= config.confidence_high_threshold
        else "medium"
        if confidence >= config.confidence_medium_threshold
        else "low"
    )
    latest_date = _as_date(result.get("latest_obs_date"))
    stale = latest_date is None or (as_of - latest_date).days > config.stale_days
    effective_risk = result.get("risk", "cannot_assess")
    severity = result.get("severity")
    if clear.empty or stale or confidence < config.confidence_medium_threshold:
        effective_risk = "cannot_assess"
        severity = None
    return {
        **result,
        "confidence": confidence,
        "confidence_label": confidence_label,
        "risk": effective_risk,
        "severity": severity,
        "is_stale": stale,
        "confidence_components": {
            "valid_fraction": valid_component,
            "persistence": persistence_component,
            "baseline_years": baseline_component,
            "baseline_stability": stability_component,
            "signal_agreement": agreement_component,
        },
    }


def apply_confidence(
    current_observations: pd.DataFrame,
    results: list[dict[str, Any]],
    as_of: date | None = None,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> list[dict[str, Any]]:
    """Apply confidence checks to each result and omit internal components."""
    output: list[dict[str, Any]] = []
    for result in results:
        field_rows = current_observations.loc[
            current_observations["field_id"].astype(str) == str(result["field_id"])
        ]
        assessed = assess_confidence(field_rows, result, as_of, config)
        assessed.pop("confidence_components", None)
        assessed.pop("is_stale", None)
        assessed.pop("if_agreement", None)
        output.append(assessed)
    return output
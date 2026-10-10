"""Robust anomaly scoring, persistence, onset, and queue ranking."""

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


def _nearest_baseline(
    baseline_rows: pd.DataFrame,
    dos: float,
    window: int,
) -> pd.Series | None:
    candidates = baseline_rows.loc[(baseline_rows["dos"] - dos).abs() <= window]
    if candidates.empty:
        return None
    index = (candidates["dos"] - dos).abs().idxmin()
    return candidates.loc[index]


def score_current(
    current_observations: pd.DataFrame,
    baseline: pd.DataFrame,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Score current observations and classify only the trailing clear run."""
    if not {"field_id", "date", "dos", "ndvi", "valid_frac"}.issubset(current_observations):
        raise ValueError("current observations must include field_id, date, dos, ndvi, valid_frac")
    if not {"field_id", "dos", "baseline_median", "baseline_sigma"}.issubset(baseline):
        raise ValueError("baseline must include field_id, dos, baseline_median, baseline_sigma")
    frame = current_observations.copy(deep=True)
    frame["date"] = frame["date"].map(_as_date)
    frame["ndvi"] = pd.to_numeric(frame["ndvi"], errors="coerce")
    frame["dos"] = pd.to_numeric(frame["dos"], errors="coerce")
    frame["valid_frac"] = pd.to_numeric(frame["valid_frac"], errors="coerce")
    frame["low_quality"] = frame.get(
        "low_quality", frame["valid_frac"].lt(config.min_valid_frac)
    ).fillna(True).astype(bool)
    frame["is_interpolated"] = frame.get(
        "is_interpolated", pd.Series(False, index=frame.index)
    ).fillna(False).astype(bool)
    baseline_by_field = {
        str(field_id): rows.sort_values("dos")
        for field_id, rows in baseline.groupby("field_id", sort=False)
    }
    medians: list[float | None] = []
    sigmas: list[float | None] = []
    years: list[int] = []
    clusters: list[int | None] = []
    for row in frame.itertuples():
        matches = baseline_by_field.get(str(row.field_id))
        matched = (
            _nearest_baseline(matches, float(row.dos), config.dos_window)
            if matches is not None and pd.notna(row.dos)
            else None
        )
        if matched is None:
            medians.append(None)
            sigmas.append(None)
            years.append(0)
            clusters.append(None)
        else:
            medians.append(float(matched["baseline_median"]))
            sigmas.append(float(matched["baseline_sigma"]))
            years.append(int(matched.get("baseline_years", 0)))
            clusters.append(int(matched["cluster"]) if pd.notna(matched.get("cluster")) else None)
    frame["baseline_median"] = medians
    frame["baseline_sigma"] = sigmas
    frame["baseline_median"] = pd.to_numeric(frame["baseline_median"], errors="coerce")
    frame["baseline_sigma"] = pd.to_numeric(frame["baseline_sigma"], errors="coerce")
    frame["baseline_years"] = years
    frame["cluster"] = clusters
    valid_ndvi = frame["ndvi"].notna() & frame["baseline_median"].notna()
    safe_baseline = frame["baseline_median"].where(frame["baseline_median"].abs() > np.finfo(float).eps)
    frame["z"] = np.where(
        valid_ndvi & frame["baseline_sigma"].gt(0),
        (frame["ndvi"] - frame["baseline_median"]) / frame["baseline_sigma"],
        np.nan,
    )
    frame["pct_dev"] = np.where(
        valid_ndvi & safe_baseline.notna(),
        (frame["ndvi"] - frame["baseline_median"]) / safe_baseline * config.percent_multiplier,
        np.nan,
    )

    field_results: list[dict[str, Any]] = []
    for field_id, group in frame.groupby("field_id", sort=True):
        group = group.sort_values("date", kind="stable")
        valid_mask = (
            group["date"].notna()
            & group["ndvi"].notna()
            & np.isfinite(group["ndvi"])
            & group["baseline_median"].notna()
            & group["baseline_sigma"].gt(0)
            & group["valid_frac"].ge(config.min_valid_frac)
            & ~group["low_quality"]
            & ~group["is_interpolated"]
        )
        clear = group.loc[valid_mask].copy()
        interpolated_break_since_low_run = False
        if clear.empty:
            trailing_low: list[pd.Series] = []
        else:
            trailing_low = []
            previous_date: date | None = None
            for index, observation in group.iterrows():
                observation_date = observation["date"]
                gap_too_large = (
                    previous_date is not None
                    and observation_date is not None
                    and (observation_date - previous_date).days > config.max_interp_gap_days
                )
                is_clear = bool(valid_mask.loc[index])
                if not is_clear or gap_too_large:
                    trailing_low = []
                    interpolated_break_since_low_run = (
                        not gap_too_large
                        and not is_clear
                        and bool(observation["is_interpolated"])
                    )
                if not is_clear:
                    previous_date = observation_date
                    continue
                is_low = float(observation["z"]) <= config.z_watch
                if not is_low:
                    trailing_low = []
                    interpolated_break_since_low_run = False
                if is_low:
                    trailing_low.append(observation)
                previous_date = observation_date
        run_length = len(trailing_low)
        latest_clear = clear.iloc[-1] if not clear.empty else None
        risk = "normal"
        severity: str | None = None
        if len(clear) < config.minimum_assessable_observations or latest_clear is None:
            risk = "cannot_assess"
        elif run_length == 1 and interpolated_break_since_low_run:
            risk = "cannot_assess"
        elif run_length > 0:
            risk = (
                "alert"
                if run_length >= config.persistence_alert_count
                else "watch"
            )
            if risk == "alert":
                high_run = sum(
                    float(row["z"]) <= config.z_high + np.finfo(float).eps * 8
                    for row in trailing_low
                )
                high_deviation = (
                    pd.notna(latest_clear["pct_dev"])
                    and float(latest_clear["pct_dev"])
                    <= -config.dev_high_pct + np.finfo(float).eps * 8
                )
                severity = (
                    "high"
                    if high_run >= config.severity_high_count or high_deviation
                    else "moderate"
                )
        if config.use_cusum and not group.empty:
            cusum = 0.0
            episode_start: date | None = None
            confirmed_onset: date | None = None
            previous_date: date | None = None
            for index, observation in group.iterrows():
                observation_date = observation["date"]
                gap_too_large = (
                    previous_date is not None
                    and observation_date is not None
                    and (observation_date - previous_date).days > config.max_interp_gap_days
                )
                is_clear = bool(valid_mask.loc[index])
                if gap_too_large:
                    cusum = 0.0
                    episode_start = None
                    confirmed_onset = None
                if not is_clear:
                    cusum = 0.0
                    episode_start = None
                    confirmed_onset = None
                    previous_date = observation_date
                    continue
                if episode_start is None:
                    episode_start = observation_date
                cusum = max(0.0, cusum + config.z_watch - float(observation["z"]) - config.cusum_drift)
                if cusum == 0.0:
                    episode_start = None
                    confirmed_onset = None
                elif cusum > config.cusum_threshold and confirmed_onset is None:
                    confirmed_onset = episode_start
                previous_date = observation_date
            if confirmed_onset is not None and risk == "normal":
                risk = "watch"
                trailing_low = [
                    clear.loc[clear["date"] >= confirmed_onset].iloc[0]
                ]
                run_length = 1
        drop_start = trailing_low[0]["date"] if risk in {"watch", "alert"} and trailing_low else None
        latest_date = latest_clear["date"] if latest_clear is not None else None
        latest_z = float(latest_clear["z"]) if latest_clear is not None else None
        pct_deficit = (
            max(0.0, -float(latest_clear["pct_dev"]))
            if latest_clear is not None and pd.notna(latest_clear["pct_dev"])
            else None
        )
        baseline_years = int(latest_clear["baseline_years"]) if latest_clear is not None else 0
        field_results.append(
            {
                "field_id": str(field_id),
                "risk": risk,
                "severity": severity,
                "confidence": 0.0,
                "confidence_label": "low",
                "z_score": latest_z,
                "pct_below_normal": pct_deficit,
                "drop_start": drop_start,
                "latest_obs_date": latest_date,
                "n_valid_obs": int(len(clear)),
                "baseline_years": baseline_years,
                "model_version": None,
                "model_score": None,
                "top_factors": None,
                "evidence": (
                    {
                        "latest_observation_date": latest_clear["date"].isoformat(),
                        "observed_ndvi": float(latest_clear["ndvi"]),
                        "baseline_median": float(latest_clear["baseline_median"]),
                        "baseline_sigma": float(latest_clear["baseline_sigma"]),
                        "z_score": latest_z,
                        "pct_below_normal": pct_deficit,
                        "baseline_years": baseline_years,
                    }
                    if latest_clear is not None
                    else None
                ),
                "decision_threshold": None,
                "rain_context": None,
                "advice_key": None,
                "advice": None,
                "priority_score": None,
                "priority_rank": None,
                "if_flag": None,
                "run_length": run_length,
                "baseline_median": (
                    float(latest_clear["baseline_median"]) if latest_clear is not None else None
                ),
                "baseline_sigma": (
                    float(latest_clear["baseline_sigma"]) if latest_clear is not None else None
                ),
            }
        )
    return frame, field_results


def rank_results(
    results: list[dict[str, Any]],
    fields: pd.DataFrame | None = None,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> list[dict[str, Any]]:
    """Calculate inspection priority and a stable one-based rank."""
    areas: dict[str, float] = {}
    if fields is not None and {"field_id", "area_ha"}.issubset(fields.columns):
        areas = dict(zip(fields["field_id"].astype(str), fields["area_ha"].astype(float)))
    risk_weight = dict(config.priority_risk_weights)
    ranked: list[dict[str, Any]] = []
    for result in results:
        item = dict(result)
        z = item.get("z_score")
        run_length = max(1, int(item.get("run_length") or 1))
        confidence = float(item.get("confidence") or 0.0)
        area_factor = areas.get(str(item["field_id"]), 1.0)
        item["priority_score"] = (
            min(abs(float(z)), config.priority_z_cap)
            * run_length
            * confidence
            * area_factor
            if z is not None and item["risk"] != "cannot_assess"
            else 0.0
        )
        item["_risk_weight"] = risk_weight.get(item["risk"], 0.0)
        ranked.append(item)
    ranked.sort(
        key=lambda item: (
            -item["_risk_weight"],
            -float(item["priority_score"] or 0.0),
            str(item["field_id"]),
        )
    )
    for rank, item in enumerate(ranked, start=1):
        item["priority_rank"] = rank
        item.pop("_risk_weight", None)
    return ranked
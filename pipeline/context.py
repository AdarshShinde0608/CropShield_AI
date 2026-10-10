"""Rainfall context and conservative plain-language advice lookup."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from .config import PIPELINE_CONFIG, PipelineConfig, day_of_season, season_bounds

ADVICE: dict[tuple[str, str], tuple[str, str]] = {
    ("alert", "dry_spell"): ("advice.inspect_moisture", "Inspect the field and check soil moisture and irrigation status."),
    ("alert", "normal"): ("advice.inspect_field", "Inspect the field and compare its condition with nearby fields."),
    ("alert", "not_applicable"): ("advice.inspect_field", "Inspect the field and review the latest clear observation."),
    ("watch", "dry_spell"): ("advice.check_moisture", "Check soil moisture and monitor the next clear observation."),
    ("watch", "normal"): ("advice.monitor_field", "Monitor the field and check the next clear observation."),
    ("watch", "not_applicable"): ("advice.monitor_field", "Monitor the field and check the next clear observation."),
    ("normal", "dry_spell"): ("advice.routine_check", "Continue routine checks and inspect soil moisture."),
    ("normal", "normal"): ("advice.routine_check", "Continue routine field checks."),
    ("normal", "not_applicable"): ("advice.routine_check", "Continue routine field checks."),
    ("cannot_assess", "dry_spell"): ("advice.check_data", "Check data availability and inspect the field if needed."),
    ("cannot_assess", "normal"): ("advice.check_data", "Check data availability before drawing conclusions."),
    ("cannot_assess", "not_applicable"): ("advice.check_data", "Check data availability before drawing conclusions."),
}


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


def compute_rainfall_features(
    rainfall: pd.DataFrame,
    baseline_season_ids: set[str] | tuple[str, ...] | list[str],
    config: PipelineConfig = PIPELINE_CONFIG,
) -> pd.DataFrame:
    """Calculate rolling rainfall and its robust baseline z-score where possible."""
    required = {"date", "rain_mm"}
    if not required.issubset(rainfall.columns):
        raise ValueError("rainfall must include date and rain_mm columns")
    frame = rainfall.copy(deep=True)
    frame["date"] = frame["date"].map(_as_date)
    frame["rain_mm"] = pd.to_numeric(frame["rain_mm"], errors="coerce")
    frame = frame.loc[
        frame["date"].notna()
        & frame["rain_mm"].notna()
        & np.isfinite(frame["rain_mm"])
    ].copy()
    if frame.empty:
        for column in ("rain14", "rain30", "rain_z"):
            frame[column] = pd.Series(dtype=float)
        return frame.reset_index(drop=True)
    if "season_id" not in frame:
        frame["rain14"] = np.nan
        frame["rain30"] = np.nan
        frame["rain_z"] = np.nan
        return frame
    frame["season_id"] = frame["season_id"].astype(str)
    if "dos" not in frame:
        frame["dos"] = [
            day_of_season(row.date, season_bounds(row.season_id)[0])
            for row in frame.itertuples()
        ]
    else:
        frame["dos"] = pd.to_numeric(frame["dos"], errors="coerce")
    frame = frame.sort_values(["season_id", "date"], kind="stable")
    pieces: list[pd.DataFrame] = []
    for _, group in frame.groupby("season_id", sort=False):
        group = group.copy()
        group["rain14"] = group["rain_mm"].rolling(
            config.rain_14_day_window, min_periods=config.rain_14_day_window
        ).sum()
        group["rain30"] = group["rain_mm"].rolling(
            config.rain_30_day_window, min_periods=config.rain_30_day_window
        ).sum()
        pieces.append(group)
    frame = pd.concat(pieces, ignore_index=True)
    if "dos" not in frame:
        frame["dos"] = np.nan
    baseline_ids = {str(value) for value in baseline_season_ids}
    is_baseline = frame["season_id"].isin(baseline_ids)
    baseline = frame.loc[is_baseline & frame["rain30"].notna()]
    rain_z = pd.Series(np.nan, index=frame.index, dtype=float)
    for index, row in frame.loc[~is_baseline & frame["rain30"].notna()].iterrows():
        baseline_near = baseline.loc[(baseline["dos"] - row["dos"]).abs() <= config.dos_window]
        values = baseline_near["rain30"].dropna()
        if values.empty:
            continue
        center = float(values.median())
        spread = max(
            config.robust_sigma_multiplier * float((values - center).abs().median()),
            config.rain_sigma_floor,
        )
        rain_z.loc[index] = (float(row["rain30"]) - center) / spread
    frame["rain_z"] = rain_z
    return frame.sort_values(["season_id", "date"], kind="stable").reset_index(drop=True)


def add_rain_context(
    field_results: list[dict[str, Any]],
    rainfall_features: pd.DataFrame,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> list[dict[str, Any]]:
    """Attach date-aligned rainfall context and translated advice keys."""
    rain_rows = rainfall_features.copy()
    if "date" in rain_rows:
        rain_rows["date"] = rain_rows["date"].map(_as_date)
        rain_rows = rain_rows.loc[rain_rows["date"].notna()].sort_values("date")
    output: list[dict[str, Any]] = []
    for result in field_results:
        item = dict(result)
        target_date = _as_date(item.get("drop_start")) or _as_date(item.get("latest_obs_date"))
        context = "not_applicable"
        if target_date is not None and not rain_rows.empty and "rain_z" in rain_rows:
            prior = rain_rows.loc[rain_rows["date"] <= target_date]
            if not prior.empty and pd.notna(prior.iloc[-1].get("rain_z")):
                context = (
                    "dry_spell"
                    if float(prior.iloc[-1]["rain_z"]) <= config.rain_dry_z_threshold
                    else "normal"
                )
        advice_key, advice = ADVICE[(item["risk"], context)]
        item["rain_context"] = context
        item["advice_key"] = advice_key
        item["advice"] = advice
        output.append(item)
    return output
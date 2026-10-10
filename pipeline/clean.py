"""Pure cleaning and date-grid regularisation for field observations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from .config import PIPELINE_CONFIG, PipelineConfig, day_of_season, season_bounds


def _observation_date(value: Any) -> date | None:
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


def _groups(frame: pd.DataFrame) -> list[tuple[tuple[Any, ...], pd.DataFrame]]:
    keys = [name for name in ("field_id", "season_id") if name in frame.columns]
    if not keys:
        return [((), frame)]
    return [
        ((key,) if not isinstance(key, tuple) else key, group.copy())
        for key, group in frame.groupby(keys, sort=False, dropna=False)
    ]


def clean_observations(
    observations: pd.DataFrame,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> pd.DataFrame:
    """Remove unusable NDVI and isolated spikes while retaining quality flags."""
    if "ndvi" not in observations.columns or "date" not in observations.columns:
        raise ValueError("observations must include date and ndvi columns")
    frame = observations.copy(deep=True)
    frame["date"] = frame["date"].map(_observation_date)
    frame = frame.loc[frame["date"].notna()].copy()
    frame["ndvi"] = pd.to_numeric(frame["ndvi"], errors="coerce")
    if "valid_frac" not in frame:
        frame["valid_frac"] = 1.0
    frame["valid_frac"] = pd.to_numeric(frame["valid_frac"], errors="coerce")
    frame["low_quality"] = frame["valid_frac"].lt(config.min_valid_frac).fillna(True)
    frame["is_interpolated"] = frame.get(
        "is_interpolated", pd.Series(False, index=frame.index)
    ).fillna(False).astype(bool)
    frame = frame.loc[
        frame["ndvi"].notna()
        & frame["ndvi"].between(config.min_valid_ndvi, config.max_valid_ndvi)
        & np.isfinite(frame["ndvi"])
    ].copy()

    kept: list[pd.DataFrame] = []
    for _, group in _groups(frame):
        group = group.sort_values("date").copy()
        values = group["ndvi"]
        previous = values.shift(1)
        following = values.shift(-1)
        neighbors = pd.concat([previous, following], axis=1).median(axis=1)
        neighbors_agree = previous.sub(following).abs().le(config.spike_delta)
        spike = (
            previous.notna()
            & following.notna()
            & neighbors_agree
            & values.sub(neighbors).abs().gt(config.spike_delta)
        )
        kept.append(group.loc[~spike])
    if not kept:
        return frame.iloc[0:0].reset_index(drop=True)
    cleaned = pd.concat(kept, ignore_index=True)
    if "season_id" in cleaned:
        cleaned["dos"] = [
            day_of_season(row.date, season_bounds(str(row.season_id))[0])
            for row in cleaned.itertuples()
        ]
    return cleaned.sort_values(
        [column for column in ("field_id", "season_id", "date") if column in cleaned],
        kind="stable",
    ).reset_index(drop=True)


def regularize_observations(
    observations: pd.DataFrame,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> pd.DataFrame:
    """Add missing grid rows, interpolating only short gaps between clear data."""
    if config.regular_grid_days <= 0:
        raise ValueError("regular_grid_days must be positive")
    frame = observations.copy(deep=True)
    frame["date"] = frame["date"].map(_observation_date)
    frame = frame.loc[frame["date"].notna()].copy()
    output: list[dict[str, Any]] = []

    for _, group in _groups(frame):
        group = group.sort_values("date").drop_duplicates("date", keep="last")
        if group.empty:
            continue
        records = group.to_dict("records")
        by_date = {record["date"]: record for record in records}
        first_date, last_date = min(by_date), max(by_date)
        grid_dates = pd.date_range(first_date, last_date, freq=f"{config.regular_grid_days}D")
        for timestamp in grid_dates:
            current_date = timestamp.date()
            if current_date in by_date:
                output.append(dict(by_date[current_date]))
                continue
            before = [d for d in by_date if d < current_date]
            after = [d for d in by_date if d > current_date]
            if not before or not after:
                continue
            left_date, right_date = max(before), min(after)
            gap_days = (right_date - left_date).days
            left, right = by_date[left_date], by_date[right_date]
            if gap_days > config.max_interp_gap_days:
                continue
            if (
                left.get("ndvi") is None
                or right.get("ndvi") is None
                or bool(left.get("low_quality", False))
                or bool(right.get("low_quality", False))
                or bool(left.get("is_interpolated", False))
                or bool(right.get("is_interpolated", False))
            ):
                continue
            fraction = (current_date - left_date).days / gap_days
            row = dict(left)
            row.update(
                date=current_date,
                ndvi=float(left["ndvi"]) + fraction * (float(right["ndvi"]) - float(left["ndvi"])),
                valid_frac=min(float(left.get("valid_frac", 1.0)), float(right.get("valid_frac", 1.0))),
                low_quality=False,
                is_interpolated=True,
            )
            if "season_id" in row:
                row["dos"] = day_of_season(
                    current_date, season_bounds(str(row["season_id"]))[0]
                )
            output.append(row)
    if not output:
        return frame.iloc[0:0].reset_index(drop=True)
    return pd.DataFrame(output).sort_values(
        [column for column in ("field_id", "season_id", "date") if column in frame],
        kind="stable",
    ).reset_index(drop=True)


def clean_and_regularize(
    observations: pd.DataFrame,
    regularize: bool = False,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> pd.DataFrame:
    """Run cleaning and, optionally, interpolation on the configured date grid."""
    cleaned = clean_observations(observations, config)
    return regularize_observations(cleaned, config) if regularize else cleaned
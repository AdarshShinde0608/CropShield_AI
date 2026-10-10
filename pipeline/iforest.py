"""Optional Isolation Forest cross-check trained on baseline observations only."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer

from .config import PIPELINE_CONFIG, PipelineConfig

FEATURE_CANDIDATES = ("ndvi", "z", "slope", "rolling_mean", "rain_z")


def _features(
    observations: pd.DataFrame,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> pd.DataFrame:
    frame = observations.copy(deep=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["ndvi"] = pd.to_numeric(frame["ndvi"], errors="coerce")
    frame = frame.sort_values(["field_id", "date"], kind="stable")
    group_columns = ["field_id"]
    if "season_id" in frame.columns:
        group_columns.append("season_id")
    grouped = frame.groupby(group_columns, sort=False)
    frame["slope"] = grouped["ndvi"].diff() / grouped["date"].diff().dt.days
    rolling_window = config.iforest_slope_window
    frame["rolling_mean"] = grouped["ndvi"].transform(
        lambda values: values.rolling(rolling_window, min_periods=1).mean()
    )
    for column in FEATURE_CANDIDATES:
        if column not in frame:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame[list(FEATURE_CANDIDATES)] = frame[list(FEATURE_CANDIDATES)].replace(
        [np.inf, -np.inf], np.nan
    )
    return frame


def flag_with_isolation_forest(
    baseline_observations: pd.DataFrame,
    current_observations: pd.DataFrame,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> tuple[pd.DataFrame, IsolationForest]:
    """Fit only baseline rows, then return current rows with score and flag."""
    if not config.use_isolation_forest:
        raise RuntimeError("Isolation Forest is disabled in PipelineConfig")
    baseline = _features(baseline_observations, config)
    current = _features(current_observations, config)
    if "low_quality" in baseline:
        baseline = baseline.loc[~baseline["low_quality"].fillna(True).astype(bool)]
    if "is_interpolated" in baseline:
        baseline = baseline.loc[~baseline["is_interpolated"].fillna(False).astype(bool)]
    baseline = baseline.loc[baseline["ndvi"].notna()]
    if len(baseline) < config.iforest_estimators:
        minimum_rows = max(2, config.baseline_cluster_min)
        if len(baseline) < minimum_rows:
            raise ValueError("Not enough clear baseline observations to fit Isolation Forest")
    feature_columns = [
        name
        for name in FEATURE_CANDIDATES
        if baseline[name].notna().any() and current[name].notna().any()
    ]
    if not feature_columns:
        raise ValueError("No shared non-empty features for Isolation Forest")
    imputer = SimpleImputer(strategy="median")
    training = imputer.fit_transform(baseline[feature_columns])
    model = IsolationForest(
        n_estimators=config.iforest_estimators,
        contamination=config.iforest_contamination,
        random_state=config.iforest_random_state,
    )
    model.fit(training)
    current_matrix = imputer.transform(current[feature_columns])
    current["if_score"] = model.decision_function(current_matrix)
    current["if_flag"] = model.predict(current_matrix) == -1
    current["date"] = current["date"].dt.date
    return current, model


def reconcile_flags(
    results: list[dict[str, Any]],
    iforest_current: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Require rule-based evidence for alerts; use IF only as corroboration."""
    iforest = iforest_current.copy()
    iforest["date"] = pd.to_datetime(iforest["date"], errors="coerce")
    output: list[dict[str, Any]] = []
    for original in results:
        item = dict(original)
        field_id = str(item["field_id"])
        rows = iforest.loc[iforest["field_id"].astype(str) == field_id].sort_values("date")
        flagged = bool(rows.iloc[-1]["if_flag"]) if not rows.empty else False
        item["if_flag"] = flagged
        rule_flagged = item["risk"] in {"watch", "alert"}
        item["if_agreement"] = rule_flagged and flagged
        if item["risk"] == "cannot_assess":
            output.append(item)
            continue
        if not (rule_flagged and flagged) and (rule_flagged or flagged):
            item["risk"] = "watch"
            item["severity"] = None
        output.append(item)
    return output
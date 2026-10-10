"""Historical field and cluster baselines without current-season leakage."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score

from .config import PIPELINE_CONFIG, PipelineConfig


def _robust_stats(values: pd.Series, config: PipelineConfig) -> tuple[float, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    clean = clean[np.isfinite(clean)]
    center = float(clean.median())
    mad = float((clean - center).abs().median())
    return center, max(config.robust_sigma_multiplier * mad, config.sigma_floor)


def _assign_clusters(
    baseline: pd.DataFrame,
    config: PipelineConfig,
) -> dict[str, int]:
    field_ids = sorted(baseline["field_id"].dropna().astype(str).unique())
    if not field_ids:
        return {}
    dos_values = sorted(baseline["dos"].dropna().astype(int).unique())
    curves = (
        baseline.groupby(["field_id", "dos"], as_index=False)["ndvi"]
        .median()
        .pivot(index="field_id", columns="dos", values="ndvi")
        .reindex(index=field_ids, columns=dos_values)
    )
    curves = curves.dropna(axis=1, how="all")
    if len(field_ids) < config.baseline_cluster_min or curves.empty:
        return {field_id: 0 for field_id in field_ids}
    matrix = SimpleImputer(strategy="median").fit_transform(curves)
    candidate_ks = range(
        config.baseline_cluster_min,
        min(config.baseline_cluster_max, len(field_ids) - 1) + 1,
    )
    best_labels = np.zeros(len(field_ids), dtype=int)
    best_silhouette = -1.0
    for cluster_count in candidate_ks:
        model = KMeans(
            n_clusters=cluster_count,
            random_state=config.cluster_random_state,
            n_init=config.cluster_n_init,
        )
        labels = model.fit_predict(matrix)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(matrix, labels))
        if score > best_silhouette:
            best_silhouette = score
            best_labels = labels
    return dict(zip(field_ids, map(int, best_labels), strict=True))


def build_baseline(
    observations: pd.DataFrame,
    baseline_season_ids: Iterable[str],
    config: PipelineConfig = PIPELINE_CONFIG,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Build ``(field_id, dos)`` robust baselines from explicitly allowed years.

    ``baseline_season_ids`` is required so callers must state which seasons are
    historical; rows outside that set can never leak into the baseline.
    """
    required = {"field_id", "season_id", "dos", "ndvi"}
    if not required.issubset(observations.columns):
        raise ValueError(f"observations must include {sorted(required)}")
    allowed = {str(value) for value in baseline_season_ids}
    if not allowed:
        raise ValueError("baseline_season_ids cannot be empty")
    frame = observations.loc[
        observations["season_id"].astype(str).isin(allowed)
    ].copy()
    if frame.empty:
        raise ValueError("no observations found for the supplied baseline seasons")
    frame["ndvi"] = pd.to_numeric(frame["ndvi"], errors="coerce")
    frame["dos"] = pd.to_numeric(frame["dos"], errors="coerce")
    if "low_quality" in frame:
        frame = frame.loc[~frame["low_quality"].fillna(True).astype(bool)]
    if "is_interpolated" in frame:
        frame = frame.loc[~frame["is_interpolated"].fillna(False).astype(bool)]
    frame = frame.loc[
        frame["ndvi"].notna()
        & frame["dos"].notna()
        & np.isfinite(frame["ndvi"])
    ].copy()
    if frame.empty:
        raise ValueError("baseline seasons contain no usable NDVI values")
    frame["dos"] = frame["dos"].astype(int)
    frame["field_id"] = frame["field_id"].astype(str)
    frame["season_id"] = frame["season_id"].astype(str)

    clusters = _assign_clusters(frame, config)
    frame["cluster"] = frame["field_id"].map(clusters)
    season_field_dos = (
        frame.groupby(["cluster", "season_id", "dos"])["ndvi"].median().reset_index()
    )
    field_ids = sorted(frame["field_id"].unique())
    dos_values = sorted(frame["dos"].unique())
    results: list[dict[str, float | int | str]] = []

    for field_id in field_ids:
        cluster = clusters[field_id]
        field_rows = frame.loc[frame["field_id"] == field_id]
        for dos in dos_values:
            local = field_rows.loc[(field_rows["dos"] - dos).abs() <= config.dos_window]
            local_years = int(local["season_id"].nunique())
            local_center, local_sigma = (
                _robust_stats(local["ndvi"], config)
                if not local.empty
                else (float("nan"), float("nan"))
            )
            cluster_rows = season_field_dos.loc[
                (season_field_dos["cluster"] == cluster)
                & ((season_field_dos["dos"] - dos).abs() <= config.dos_window)
            ]
            cluster_center, cluster_sigma = (
                _robust_stats(cluster_rows["ndvi"], config)
                if not cluster_rows.empty
                else (float("nan"), float("nan"))
            )
            if local_years < config.min_baseline_years:
                center = cluster_center
            else:
                center = local_center
            if np.isnan(center):
                continue
            sigma = (
                local_sigma
                if np.isnan(cluster_sigma)
                else cluster_sigma
                if np.isnan(local_sigma)
                else (local_sigma + cluster_sigma) / 2
            )
            results.append(
                {
                    "field_id": field_id,
                    "dos": int(dos),
                    "baseline_median": float(center),
                    "baseline_sigma": max(float(sigma), config.sigma_floor),
                    "baseline_years": local_years,
                    "cluster": cluster,
                }
            )
    return pd.DataFrame(results), clusters
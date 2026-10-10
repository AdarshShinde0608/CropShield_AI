"""Pure baseline comparison and evidence-based onset helpers."""

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from .config import PIPELINE_CONFIG, PipelineConfig
from .quality import _as_date, _finite_number


def _nearest_baseline(
    baseline_rows: list[Mapping[str, object]],
    dos: float,
    window: int,
    field_id: object,
) -> Mapping[str, object] | None:
    eligible: list[tuple[float, int, Mapping[str, object]]] = []
    for index, baseline in enumerate(baseline_rows):
        if field_id is not None and baseline.get("field_id", field_id) != field_id:
            continue
        baseline_dos = _finite_number(baseline.get("dos"))
        if baseline_dos is None:
            continue
        distance = abs(baseline_dos - dos)
        if distance <= window:
            eligible.append((distance, index, baseline))
    if not eligible:
        return None
    return min(eligible, key=lambda item: (item[0], item[1]))[2]


def build_baseline_evidence(
    observations: Iterable[Mapping[str, object]],
    baseline_rows: Iterable[Mapping[str, object]],
    config: PipelineConfig = PIPELINE_CONFIG,
) -> dict[str, Any]:
    """Compare observations to supplied per-DOS median/bands and report trailing onset.

    Baseline rows supply ``dos``, ``baseline_median``, and either explicit
    ``baseline_lower``/``baseline_upper`` bounds or ``baseline_sigma`` (used as
    a symmetric one-sigma band). Onset is the first date in the latest unbroken
    run of clear observations below the lower band, once configured persistence
    is met. This evidence does not assign risk, severity, or confidence.
    """
    baselines = list(baseline_rows)
    source = list(observations)
    ordered = sorted(
        enumerate(source),
        key=lambda pair: (_as_date(pair[1].get("date")) or date.min, pair[0]),
    )
    evidence: list[dict[str, object]] = []
    trailing_below: list[date] = []
    previous_date: date | None = None

    for _, observation in ordered:
        observation_date = _as_date(observation.get("date"))
        dos = _finite_number(observation.get("dos"))
        ndvi = _finite_number(observation.get("ndvi"))
        field_id = observation.get("field_id")
        baseline = (
            _nearest_baseline(baselines, dos, config.dos_window, field_id)
            if dos is not None
            else None
        )
        median = _finite_number(baseline.get("baseline_median")) if baseline else None
        lower = _finite_number(baseline.get("baseline_lower")) if baseline else None
        upper = _finite_number(baseline.get("baseline_upper")) if baseline else None
        sigma = _finite_number(baseline.get("baseline_sigma")) if baseline else None
        if median is not None and lower is None and upper is None and sigma is not None and sigma >= 0.0:
            lower = median - sigma
            upper = median + sigma
        valid_frac = _finite_number(observation.get("valid_frac"))
        valid_band = (
            median is not None
            and lower is not None
            and upper is not None
            and lower <= median <= upper
        )
        is_clear = (
            observation_date is not None
            and ndvi is not None
            and config.min_valid_ndvi <= ndvi <= config.max_valid_ndvi
            and valid_frac is not None
            and 0.0 <= valid_frac <= 1.0
            and valid_frac >= config.min_valid_frac
            and observation.get("low_quality", False) is False
            and observation.get("is_interpolated", False) is False
            and valid_band
        )
        if previous_date is not None and observation_date is not None:
            if (observation_date - previous_date).days > config.max_interp_gap_days:
                trailing_below = []
        below_band = bool(is_clear and ndvi is not None and lower is not None and ndvi < lower)
        if not is_clear or not below_band:
            trailing_below = []
        elif observation_date is not None:
            trailing_below.append(observation_date)
        evidence.append(
            {
                "date": observation_date,
                "dos": dos,
                "ndvi": ndvi,
                "baseline_median": median,
                "baseline_lower": lower,
                "baseline_upper": upper,
                "deviation_from_median": (
                    ndvi - median if ndvi is not None and median is not None else None
                ),
                "below_baseline_band": below_band,
                "is_clear": is_clear,
            }
        )
        if observation_date is not None:
            previous_date = observation_date

    onset = (
        trailing_below[0]
        if len(trailing_below) >= config.persistence_alert_count
        else None
    )
    return {"observations": evidence, "drop_start": onset}

"""Pre-inference data-quality checks independent of any ML framework."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Literal

from .config import PIPELINE_CONFIG, PipelineConfig


@dataclass(frozen=True)
class QualityGateResult:
    """Assessability only; this gate does not assign a stress risk."""

    assessable: bool
    risk: Literal["cannot_assess"] | None
    reason: str | None
    clear_observations: int
    latest_clear_date: date | None


def _as_date(value: object) -> date | None:
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


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def assess_data_quality(
    observations: Iterable[Mapping[str, object]],
    as_of: date | None = None,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> QualityGateResult:
    """Return cannot_assess when clear-observation count or freshness is insufficient."""
    effective_date = as_of or date.today()
    clear_dates: list[date] = []
    for observation in observations:
        observation_date = _as_date(observation.get("date"))
        ndvi = _finite_number(observation.get("ndvi"))
        valid_frac = _finite_number(observation.get("valid_frac"))
        if (
            observation_date is None
            or observation_date > effective_date
            or ndvi is None
            or ndvi < config.min_valid_ndvi
            or ndvi > config.max_valid_ndvi
            or valid_frac is None
            or not 0.0 <= valid_frac <= 1.0
            or valid_frac < config.min_valid_frac
            or observation.get("low_quality", False) is not False
            or observation.get("is_interpolated", False) is not False
        ):
            continue
        clear_dates.append(observation_date)

    latest_clear = max(clear_dates, default=None)
    if len(clear_dates) < config.minimum_assessable_observations:
        return QualityGateResult(
            assessable=False,
            risk="cannot_assess",
            reason="too_few_clear_observations",
            clear_observations=len(clear_dates),
            latest_clear_date=latest_clear,
        )
    if latest_clear is None or (effective_date - latest_clear).days > config.stale_days:
        return QualityGateResult(
            assessable=False,
            risk="cannot_assess",
            reason="stale_observation",
            clear_observations=len(clear_dates),
            latest_clear_date=latest_clear,
        )
    return QualityGateResult(
        assessable=True,
        risk=None,
        reason=None,
        clear_observations=len(clear_dates),
        latest_clear_date=latest_clear,
    )

"""Shared, immutable pipeline settings and calendar helpers."""

from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True)
class PipelineConfig:
    season_start_month: int = 11
    season_start_day: int = 1
    season_end_month: int = 3
    season_end_day: int = 31
    baseline_seasons: tuple[str, ...] = (
        "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"
    )
    current_season: str = "2025-26"
    min_valid_frac: float = 0.5
    min_valid_ndvi: float = -0.1
    max_valid_ndvi: float = 1.0
    spike_delta: float = 0.2
    max_interp_gap_days: int = 20
    regular_grid_days: int = 5
    dos_window: int = 12
    min_baseline_years: int = 3
    sigma_floor: float = 0.05
    robust_sigma_multiplier: float = 1.4826
    z_watch: float = -1.5
    z_high: float = -2.0
    dev_high_pct: float = 20.0
    stale_days: int = 20
    cs_threshold: float = 0.6
    persistence_alert_count: int = 2
    severity_high_count: int = 2
    baseline_cluster_min: int = 2
    baseline_cluster_max: int = 4
    cluster_random_state: int = 42
    cluster_n_init: int = 10
    minimum_assessable_observations: int = 2
    recent_observation_count: int = 3
    confidence_medium_threshold: float = 0.5
    confidence_high_threshold: float = 0.8
    confidence_valid_frac_weight: float = 0.30
    confidence_persistence_weight: float = 0.25
    confidence_baseline_years_weight: float = 0.20
    confidence_baseline_stability_weight: float = 0.15
    confidence_signal_agreement_weight: float = 0.10
    confidence_isolation_forest_bonus: float = 0.03
    priority_z_cap: float = 4.0
    priority_risk_weights: tuple[tuple[str, float], ...] = (
        ("alert", 3.0),
        ("watch", 2.0),
        ("normal", 1.0),
        ("cannot_assess", 0.0),
    )
    percent_multiplier: float = 100.0
    use_cusum: bool = False
    cusum_drift: float = 0.5
    cusum_threshold: float = 4.0
    use_isolation_forest: bool = False
    iforest_estimators: int = 200
    iforest_contamination: float = 0.05
    iforest_random_state: int = 42
    iforest_slope_window: int = 3
    worldcover_cropland_class: int = 40
    sentinel_scale_meters: int = 10
    chirps_scale_meters: int = 5566
    gee_max_pixels: int = 1_000_000
    sentinel_collection_id: str = "COPERNICUS/S2_SR_HARMONIZED"
    cloud_score_collection_id: str = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
    worldcover_collection_id: str = "ESA/WorldCover/v200"
    chirps_collection_id: str = "UCSB-CHG/CHIRPS/DAILY"
    rain_14_day_window: int = 14
    rain_30_day_window: int = 30
    rain_dry_z_threshold: float = -1.0
    rain_sigma_floor: float = 0.1
    evaluation_calibration_bins: int = 10
    threshold_sweep_watch_start: float = -1.0
    threshold_sweep_watch_stop: float = -2.5
    threshold_sweep_watch_step: float = -0.5
    threshold_sweep_persistence_min: int = 1
    threshold_sweep_persistence_max: int = 3
    injection_magnitudes: tuple[float, ...] = (0.75, 0.80, 0.85)
    injection_starts_per_curve: int = 1
    injection_min_start_fraction: float = 0.25
    fixed_ndvi_threshold: float = 0.30
    random_state: int = 42
    ee_retry_count: int = 3
    ee_retry_base_seconds: float = 1.0
    extraction_chunk_days: int = 15


PIPELINE_CONFIG = PipelineConfig()
MODEL_FEATURE_EPSILON = 1e-6


def config_parameters(config: PipelineConfig = PIPELINE_CONFIG) -> dict[str, object]:
    """Return a JSON-serializable snapshot of the exact run configuration."""
    return asdict(config)


def season_bounds(
    label: str,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> tuple[date, date]:
    """Return configured rabi bounds for an adjacent-year ``YYYY-YY`` label."""
    try:
        start_text, end_text = label.split("-", maxsplit=1)
        start_year = int(start_text)
        end_year = int(end_text)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid season label: {label!r}") from exc
    if end_year != (start_year + 1) % 100:
        raise ValueError(f"Season label must span adjacent years: {label!r}")
    return (
        date(start_year, config.season_start_month, config.season_start_day),
        date(start_year + 1, config.season_end_month, config.season_end_day),
    )


def day_of_season(value: date, season_start: date) -> int:
    """Return one-based day-of-season for a date and its season start."""
    return (value - season_start).days + 1


MIN_VALID_FRAC = PIPELINE_CONFIG.min_valid_frac
SPIKE_DELTA = PIPELINE_CONFIG.spike_delta
MAX_INTERP_GAP_DAYS = PIPELINE_CONFIG.max_interp_gap_days
DOS_WINDOW = PIPELINE_CONFIG.dos_window
MIN_BASELINE_YEARS = PIPELINE_CONFIG.min_baseline_years
SIGMA_FLOOR = PIPELINE_CONFIG.sigma_floor
Z_WATCH = PIPELINE_CONFIG.z_watch
Z_HIGH = PIPELINE_CONFIG.z_high
DEV_HIGH_PCT = PIPELINE_CONFIG.dev_high_pct
STALE_DAYS = PIPELINE_CONFIG.stale_days
CS_THRESHOLD = PIPELINE_CONFIG.cs_threshold

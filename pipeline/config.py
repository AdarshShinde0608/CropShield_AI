"""Pipeline compatibility surface; shared configuration lives in cropshield_core."""

from packages.cropshield_core import config as _shared_config

CS_THRESHOLD = _shared_config.CS_THRESHOLD
DEV_HIGH_PCT = _shared_config.DEV_HIGH_PCT
DOS_WINDOW = _shared_config.DOS_WINDOW
MAX_INTERP_GAP_DAYS = _shared_config.MAX_INTERP_GAP_DAYS
MIN_BASELINE_YEARS = _shared_config.MIN_BASELINE_YEARS
MIN_VALID_FRAC = _shared_config.MIN_VALID_FRAC
MODEL_FEATURE_EPSILON = _shared_config.MODEL_FEATURE_EPSILON
PIPELINE_CONFIG = _shared_config.PIPELINE_CONFIG
SIGMA_FLOOR = _shared_config.SIGMA_FLOOR
SPIKE_DELTA = _shared_config.SPIKE_DELTA
STALE_DAYS = _shared_config.STALE_DAYS
Z_HIGH = _shared_config.Z_HIGH
Z_WATCH = _shared_config.Z_WATCH
PipelineConfig = _shared_config.PipelineConfig
config_parameters = _shared_config.config_parameters
day_of_season = _shared_config.day_of_season
season_bounds = _shared_config.season_bounds

SEED_VALUE = 20261019
SEED_RUN_ID = "synthetic-demo-seed-v1"
SEED_RUN_NOTES = "SYNTHETIC demo data; not Earth Engine or field measurements"
SEED_INDEX = "NDVI"
SECTION_5_COLLECTIONS = (
    "users",
    "regions",
    "fields",
    "seasons",
    "observations",
    "rainfall",
    "field_results",
    "analysis_runs",
    "validation_reports",
    "actions",
)
REGION_ID = "demo-region"
REGION_NAME = "Demo Region (synthetic)"
REGION_STATE = "Maharashtra"
REGION_CENTER_LATITUDE = 19.0
REGION_CENTER_LONGITUDE = 73.0
FIELD_COUNT = 40
FIELD_GRID_COLUMNS = 8
FIELD_SIDE_METERS = 200.0
FIELD_GRID_SPACING_METERS = 220.0
METERS_PER_LATITUDE_DEGREE = 111_320.0
FIELD_OFFSET_STEP = 0.003
FIELD_OFFSET_CENTER = 3
FIELD_OFFSET_MODULUS = 7
SEED_SEASON_START_MONTH = 11
SEED_SEASON_START_DAY = 1
SEED_SEASON_END_MONTH = 3
SEED_SEASON_END_DAY = 31
BASELINE_START_YEAR = 2019
BASELINE_SEASON_COUNT = 6
CURRENT_SEASON_START_YEAR = 2025
OBSERVATION_INTERVAL_DAYS = 10
PEAK_DAY_OF_SEASON = 90
MINIMUM_SEASON_LENGTH_DAYS = 151
NDVI_AT_SOWING = 0.18
NDVI_AT_PEAK = 0.72
NDVI_AT_HARVEST = 0.36
NORMAL_NOISE_MAX_ABSOLUTE = 0.018
MIN_NDVI = 0.0
MAX_NDVI = 1.0
CLOUD_GAP_PROBABILITY = 0.12
CLOUDY_FIELD_GAP_PROBABILITY = 0.90
CLOUDY_FIELD_COUNT = 3
CLOUDY_FIELD_VALID_FRACTION_MAX = 0.25
MAX_CLOUD_GAP_VALID_FRACTION = 0.35
MINIMUM_VALID_FRACTION = 0.50
MINIMUM_CLOUD_VALID_FRACTION = 0.02
MAXIMUM_NORMAL_VALID_FRACTION = 1.0
MINIMUM_NORMAL_VALID_FRACTION = 0.58
MINIMUM_ASSESSABLE_OBSERVATIONS = 5
MINIMUM_PERSISTENT_ANOMALIES = 2
BASELINE_SIGMA_FLOOR = 0.05
ROBUST_SIGMA_MULTIPLIER = 1.4826
WATCH_PCT_BELOW_BASELINE = 15.0
ALERT_PCT_BELOW_BASELINE = 40.0
HIGH_SEVERITY_PCT_BELOW_BASELINE = 55.0
STRESS_FIELD_COUNT = 8
STRESS_START_DAYS_OF_SEASON = (55, 65, 75, 85, 95, 105, 115, 120)
STRESS_PCT_REDUCTIONS = (62.0, 48.0, 43.0, 32.0, 29.0, 26.0, 24.0, 22.0)
DRY_SPELL_START_DOS = 95
DRY_SPELL_END_DOS = 125
NORMAL_RAIN_MM_PER_DAY = 2.0
DRY_SPELL_RAIN_MM_PER_DAY = 0.1
DRY_SPELL_RAIN_Z = -1.8
NORMAL_RAIN_Z = 0.1
CONFIDENCE_MEDIUM_THRESHOLD = 0.5
CONFIDENCE_HIGH_THRESHOLD = 0.8
CONFIDENCE_MAX = 1.0
OUTPUT_DECIMAL_PLACES = 4
OBSERVATION_DECIMAL_PLACES = 3
INDEX_DECIMAL_PLACES = 2
BASELINE_SIGMA_DECIMAL_PLACES = 4
ZSCORE_DECIMAL_PLACES = 3
CONFIDENCE_DECIMAL_PLACES = 3
RISK_SCORE_DECIMAL_PLACES = 4
RAIN_DECIMAL_PLACES = 2
PERCENTILE_MIN = 0.0
PERCENTILE_MAX = 1.0
STRESS_REDUCTION_DENOMINATOR = 100.0
PERCENT_DENOMINATOR = 100.0
FIELD_AREA_SQUARE_METERS_PER_HECTARE = 10_000.0
POLYGON_EDGE_COUNT = 4
TRAILING_RAIN_14_OBSERVATION_COUNT = 2
TRAILING_RAIN_30_OBSERVATION_COUNT = 3
RAINFALL_STEP_DAYS = 1
RAINFALL_14_DAY_WINDOW = 14
RAINFALL_30_DAY_WINDOW = 30
MIN_RAIN_MM = 0.0
PERCENT_REDUCTION_DENOMINATOR = 100.0
PERCENT_MULTIPLIER = 100.0
RECENT_OBSERVATION_COUNT = 3
RECENT_ANOMALY_PERCENT_COUNT = 100.0
NDVI_INDEX_PERCENT_MULTIPLIER = 100.0
SECONDS_PER_DAY = 86_400
RING_CLOSURE_VERTEX_COUNT = 1
FIELD_ID_PAD_WIDTH = 3
FIELD_NAME_PAD_WIDTH = 2
RISK_PRIORITY_WEIGHTS = {
    "alert": 3.0,
    "watch": 2.0,
    "normal": 1.0,
    "cannot_assess": 0.0,
}


def seed_parameters(seed: int = SEED_VALUE) -> dict[str, object]:
    """Return the configuration snapshot recorded on the synthetic analysis run."""
    return {
        **config_parameters(),
        "seed": seed,
        "run_id": SEED_RUN_ID,
        "index": SEED_INDEX,
        "section_5_collections": list(SECTION_5_COLLECTIONS),
        "region_id": REGION_ID,
        "region_name": REGION_NAME,
        "region_state": REGION_STATE,
        "run_notes": SEED_RUN_NOTES,
        "field_grid_columns": FIELD_GRID_COLUMNS,
        "field_side_m": FIELD_SIDE_METERS,
        "field_grid_spacing_m": FIELD_GRID_SPACING_METERS,
        "field_count": FIELD_COUNT,
        "field_center_latitude": REGION_CENTER_LATITUDE,
        "field_center_longitude": REGION_CENTER_LONGITUDE,
        "meters_per_latitude_degree": METERS_PER_LATITUDE_DEGREE,
        "field_offset_step": FIELD_OFFSET_STEP,
        "field_offset_center": FIELD_OFFSET_CENTER,
        "field_offset_modulus": FIELD_OFFSET_MODULUS,
        "baseline_start_year": BASELINE_START_YEAR,
        "baseline_seasons": BASELINE_SEASON_COUNT,
        "current_season": f"{CURRENT_SEASON_START_YEAR}-{str(CURRENT_SEASON_START_YEAR + 1)[-2:]}",
        "season_start_month": SEED_SEASON_START_MONTH,
        "season_start_day": SEED_SEASON_START_DAY,
        "season_end_month": SEED_SEASON_END_MONTH,
        "season_end_day": SEED_SEASON_END_DAY,
        "observation_interval_days": OBSERVATION_INTERVAL_DAYS,
        "season_length_days": MINIMUM_SEASON_LENGTH_DAYS,
        "peak_day_of_season": PEAK_DAY_OF_SEASON,
        "ndvi_at_sowing": NDVI_AT_SOWING,
        "ndvi_at_peak": NDVI_AT_PEAK,
        "ndvi_at_harvest": NDVI_AT_HARVEST,
        "normal_noise_max_absolute": NORMAL_NOISE_MAX_ABSOLUTE,
        "cloud_gap_probability": CLOUD_GAP_PROBABILITY,
        "cloudy_field_gap_probability": CLOUDY_FIELD_GAP_PROBABILITY,
        "cloudy_field_count": CLOUDY_FIELD_COUNT,
        "cloudy_field_valid_fraction_max": CLOUDY_FIELD_VALID_FRACTION_MAX,
        "maximum_cloud_gap_valid_fraction": MAX_CLOUD_GAP_VALID_FRACTION,
        "minimum_cloud_valid_fraction": MINIMUM_CLOUD_VALID_FRACTION,
        "maximum_normal_valid_fraction": MAXIMUM_NORMAL_VALID_FRACTION,
        "minimum_normal_valid_fraction": MINIMUM_NORMAL_VALID_FRACTION,
        "minimum_valid_fraction": MINIMUM_VALID_FRACTION,
        "minimum_assessable_observations": MINIMUM_ASSESSABLE_OBSERVATIONS,
        "minimum_persistent_anomalies": MINIMUM_PERSISTENT_ANOMALIES,
        "baseline_sigma_floor": BASELINE_SIGMA_FLOOR,
        "robust_sigma_multiplier": ROBUST_SIGMA_MULTIPLIER,
        "watch_pct_below_baseline": WATCH_PCT_BELOW_BASELINE,
        "alert_pct_below_baseline": ALERT_PCT_BELOW_BASELINE,
        "high_severity_pct_below_baseline": HIGH_SEVERITY_PCT_BELOW_BASELINE,
        "stress_start_days_of_season": list(STRESS_START_DAYS_OF_SEASON),
        "stress_pct_reductions": list(STRESS_PCT_REDUCTIONS),
        "stress_field_count": STRESS_FIELD_COUNT,
        "dry_spell_start_dos": DRY_SPELL_START_DOS,
        "dry_spell_end_dos": DRY_SPELL_END_DOS,
        "normal_rain_mm_per_day": NORMAL_RAIN_MM_PER_DAY,
        "dry_spell_rain_mm_per_day": DRY_SPELL_RAIN_MM_PER_DAY,
        "rainfall_step_days": RAINFALL_STEP_DAYS,
        "rainfall_14_day_window": RAINFALL_14_DAY_WINDOW,
        "rainfall_30_day_window": RAINFALL_30_DAY_WINDOW,
        "minimum_rain_mm": MIN_RAIN_MM,
        "dry_spell_rain_z": DRY_SPELL_RAIN_Z,
        "normal_rain_z": NORMAL_RAIN_Z,
        "confidence_medium_threshold": CONFIDENCE_MEDIUM_THRESHOLD,
        "confidence_high_threshold": CONFIDENCE_HIGH_THRESHOLD,
        "confidence_max": CONFIDENCE_MAX,
        "ndvi_min": MIN_NDVI,
        "ndvi_max": MAX_NDVI,
        "output_decimal_places": OUTPUT_DECIMAL_PLACES,
        "observation_decimal_places": OBSERVATION_DECIMAL_PLACES,
        "index_decimal_places": INDEX_DECIMAL_PLACES,
        "baseline_sigma_decimal_places": BASELINE_SIGMA_DECIMAL_PLACES,
        "zscore_decimal_places": ZSCORE_DECIMAL_PLACES,
        "confidence_decimal_places": CONFIDENCE_DECIMAL_PLACES,
        "risk_score_decimal_places": RISK_SCORE_DECIMAL_PLACES,
        "rain_decimal_places": RAIN_DECIMAL_PLACES,
        "risk_priority_weights": RISK_PRIORITY_WEIGHTS.copy(),
        "stress_reduction_denominator": STRESS_REDUCTION_DENOMINATOR,
        "percent_denominator": PERCENT_DENOMINATOR,
        "percent_multiplier": PERCENT_MULTIPLIER,
        "percent_reduction_denominator": PERCENT_REDUCTION_DENOMINATOR,
        "field_area_square_meters_per_hectare": FIELD_AREA_SQUARE_METERS_PER_HECTARE,
        "trailing_rain_14_observation_count": TRAILING_RAIN_14_OBSERVATION_COUNT,
        "trailing_rain_30_observation_count": TRAILING_RAIN_30_OBSERVATION_COUNT,
        "recent_observation_count": RECENT_OBSERVATION_COUNT,
        "field_id_pad_width": FIELD_ID_PAD_WIDTH,
        "field_name_pad_width": FIELD_NAME_PAD_WIDTH,
        "is_synthetic": True,
    }
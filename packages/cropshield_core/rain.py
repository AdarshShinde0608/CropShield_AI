"""Rain-context classification shared by pipeline and inference consumers."""

from math import isfinite

from .config import PIPELINE_CONFIG, PipelineConfig


def rain_context_from_z(
    rain_z: float | None,
    config: PipelineConfig = PIPELINE_CONFIG,
) -> str:
    """Map an available rainfall z-score to dry_spell/normal; missing stays unavailable."""
    if rain_z is None or not isfinite(rain_z):
        return "not_applicable"
    return "dry_spell" if rain_z <= config.rain_dry_z_threshold else "normal"

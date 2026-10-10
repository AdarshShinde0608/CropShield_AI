"""Input validation and derived features for the audited crop-type model."""

from collections.abc import Mapping
from math import isfinite
from typing import Final

from .config import MODEL_FEATURE_EPSILON


MODEL_FEATURE_NAMES: Final[tuple[str, ...]] = (
    "NDVI",
    "NDWI",
    "EVI",
    "GNDVI",
    "SAVI",
    "Red",
    "Green",
    "Blue",
    "NIR",
    "SWIR",
    "NIR_Red_ratio",
    "NDMI",
    "Red_NIR_diff",
    "is_kharif",
)

_REQUIRED_NUMERIC_FEATURES: Final[tuple[str, ...]] = MODEL_FEATURE_NAMES[:10]
def build_crop_type_features(row: Mapping[str, object]) -> dict[str, float | int]:
    """Build one audited row with no undocumented window or scaler transformations."""
    missing = [name for name in _REQUIRED_NUMERIC_FEATURES if name not in row]
    if "Season" not in row:
        missing.append("Season")
    if missing:
        raise ValueError(f"Missing crop-type model inputs: {', '.join(missing)}")

    features: dict[str, float | int] = {}
    for name in _REQUIRED_NUMERIC_FEATURES:
        value = row[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Crop-type input {name} must be a finite number")
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError(f"Crop-type input {name} must be a finite number")
        features[name] = numeric

    nir = features["NIR"]
    red = features["Red"]
    swir = features["SWIR"]
    assert isinstance(nir, float) and isinstance(red, float) and isinstance(swir, float)
    ratio_denominator = red + MODEL_FEATURE_EPSILON
    ndmi_denominator = nir + swir + MODEL_FEATURE_EPSILON
    if ratio_denominator == 0.0 or ndmi_denominator == 0.0:
        raise ValueError("Crop-type input bands produce a zero derived-feature denominator")
    derived = {
        "NIR_Red_ratio": nir / ratio_denominator,
        "NDMI": (nir - swir) / ndmi_denominator,
        "Red_NIR_diff": nir - red,
    }
    if not all(isfinite(value) for value in derived.values()):
        raise ValueError("Crop-type inputs produce a non-finite derived feature")
    features.update(derived)
    season = row["Season"]
    if not isinstance(season, str):
        raise ValueError("Crop-type input Season must be a string")
    features["is_kharif"] = int(season == "Kharif")
    return features

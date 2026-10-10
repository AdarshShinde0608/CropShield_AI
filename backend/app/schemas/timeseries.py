from datetime import date
from pydantic import BaseModel, ConfigDict, Field


class TimeseriesPoint(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "date": "2026-01-04",
                "ndvi": 0.51,
                "baseline_median": 0.58,
                "band_low": 0.52,
                "band_high": 0.64,
                "z": -0.9,
                "low_quality": False,
                "is_interpolated": False,
            }
        },
    )

    date: date
    ndvi: float | None = None
    baseline_median: float | None = None
    band_low: float | None = None
    band_high: float | None = None
    z: float | None = None
    low_quality: bool = False
    is_interpolated: bool = False


class RainPoint(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {"date": "2026-01-04", "rain_mm": 0.0, "rain30": 4.2}
        },
    )

    date: date
    rain_mm: float | None = None
    rain14: float | None = None
    rain30: float | None = None


class TimeseriesResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "field_id": "F012",
                "drop_start": "2026-01-14",
                "points": [
                    {
                        "date": "2026-01-04",
                        "ndvi": 0.51,
                        "baseline_median": 0.58,
                        "band_low": 0.52,
                        "band_high": 0.64,
                        "z": -0.9,
                        "low_quality": False,
                        "is_interpolated": False,
                    }
                ],
                "rainfall": [{"date": "2026-01-04", "rain_mm": 0.0, "rain30": 4.2}],
            }
        },
    )

    field_id: str
    drop_start: date | None = None
    points: list[TimeseriesPoint] = Field(default_factory=list)
    rainfall: list[RainPoint] = Field(default_factory=list)
from typing import Literal

from math import isfinite
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.result import FieldResult


class GeoJSONPolygon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]] = Field(min_length=1)

    @field_validator("coordinates")
    @classmethod
    def validate_polygon_rings(
        cls,
        rings: list[list[list[float]]],
    ) -> list[list[list[float]]]:
        for ring in rings:
            if len(ring) < 4:
                raise ValueError("Polygon rings must contain at least four positions")
            if ring[0] != ring[-1]:
                raise ValueError("Polygon rings must be closed")
            for position in ring:
                if len(position) not in (2, 3):
                    raise ValueError("GeoJSON positions must have two or three coordinates")
                if not all(isfinite(value) for value in position):
                    raise ValueError("GeoJSON coordinates must be finite numbers")
                longitude, latitude = position[:2]
                if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                    raise ValueError("GeoJSON longitude or latitude is out of range")
        return rings


class FieldFeature(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.0, 19.0], [73.1, 19.0], [73.1, 19.1], [73.0, 19.0]]],
                },
                "properties": {
                    "field_id": "F012",
                    "risk": "watch",
                    "severity": None,
                    "confidence": 0.75,
                    "confidence_label": "medium",
                    "z_score": -1.6,
                    "pct_below_normal": 16.0,
                    "drop_start": "2026-01-14",
                    "latest_obs_date": "2026-02-08",
                    "n_valid_obs": 3,
                    "baseline_years": 6,
                    "rain_context": "normal",
                    "advice_key": "advice.inspect_field",
                    "advice": "Inspect this field and check recent conditions.",
                    "priority_score": 1.2,
                    "priority_rank": 1,
                    "if_flag": None,
                    "is_synthetic": True,
                },
            }
        },
    )

    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONPolygon | None
    properties: FieldResult


class FieldCollection(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[73.0, 19.0], [73.1, 19.0], [73.1, 19.1], [73.0, 19.0]]],
                        },
                        "properties": {
                            "field_id": "F012",
                            "risk": "normal",
                            "severity": None,
                            "confidence": 0.9,
                            "confidence_label": "high",
                            "n_valid_obs": 5,
                            "baseline_years": 6,
                            "is_synthetic": True,
                        },
                    }
                ],
            }
        },
    )

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[FieldFeature]
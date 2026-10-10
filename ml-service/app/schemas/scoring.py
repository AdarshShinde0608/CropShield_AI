from __future__ import annotations

from datetime import date
import re
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    field_validator,
    model_validator,
)

NonEmptyId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^\S(?:.*\S)?$")]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SpectralIndices(StrictRequest):
    NDVI: Annotated[FiniteFloat, Field(ge=-1.0, le=1.0)]
    NDWI: FiniteFloat
    EVI: FiniteFloat
    GNDVI: FiniteFloat
    SAVI: FiniteFloat


class SpectralBands(StrictRequest):
    Red: FiniteFloat
    Green: FiniteFloat
    Blue: FiniteFloat
    NIR: FiniteFloat
    SWIR: FiniteFloat


class Observation(StrictRequest):
    date: date
    dos: Annotated[int, Field(ge=1)]
    ndvi: Annotated[FiniteFloat, Field(ge=-1.0, le=1.0)]
    valid_frac: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
    season: Annotated[str, Field(min_length=1, max_length=32)]
    low_quality: bool = False
    is_interpolated: bool = False
    indices: SpectralIndices
    bands: SpectralBands
    baseline_median: FiniteFloat | None = None
    baseline_sigma: Annotated[FiniteFloat, Field(ge=0.0)] | None = None
    baseline_lower: FiniteFloat | None = None
    baseline_upper: FiniteFloat | None = None
    rain_z: FiniteFloat | None = None

    @field_validator("date", mode="before")
    @classmethod
    def require_iso_date(cls, value: object) -> date:
        if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise ValueError("date must use YYYY-MM-DD format")
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("date must be a valid calendar date") from error

    @model_validator(mode="after")
    def ndvi_matches_indices(self) -> "Observation":
        if self.ndvi != self.indices.NDVI:
            raise ValueError("ndvi must match indices.NDVI")
        return self


class BaselineObservation(StrictRequest):
    dos: Annotated[int, Field(ge=1)]
    baseline_median: FiniteFloat
    baseline_sigma: Annotated[FiniteFloat, Field(ge=0.0)] | None = None
    baseline_lower: FiniteFloat | None = None
    baseline_upper: FiniteFloat | None = None


class ScoreRequest(StrictRequest):
    field_id: NonEmptyId
    observations: Annotated[list[Observation], Field(min_length=1)]
    baseline_observations: list[BaselineObservation] = Field(default_factory=list)
    decision_threshold: Annotated[FiniteFloat, Field(ge=0.0, le=1.0)] | None = None

    @model_validator(mode="after")
    def unique_observation_dates(self) -> "ScoreRequest":
        dates = [observation.date for observation in self.observations]
        if len(dates) != len(set(dates)):
            raise ValueError("observations must not contain duplicate dates")
        return self


class ScoreBatchRequest(StrictRequest):
    items: Annotated[list[ScoreRequest], Field(min_length=1)]


class BaselineEvidenceItem(BaseModel):
    date: date | None
    dos: float | None
    ndvi: float | None
    baseline_median: float | None
    baseline_lower: float | None
    baseline_upper: float | None
    deviation_from_median: float | None
    below_baseline_band: bool
    is_clear: bool


class Evidence(BaseModel):
    observations: list[BaselineEvidenceItem]


class ScoreResponse(BaseModel):
    field_id: str
    risk: Literal["normal", "watch", "alert", "cannot_assess"]
    severity: Literal["moderate", "high"] | None
    confidence: float | None
    confidence_label: Literal["high", "medium", "low"] | None
    model_score: float | None
    top_factors: list[str] | dict[str, float] | None
    evidence: Evidence
    drop_start: date | None
    rain_context: str
    model_version: str | None
    decision_threshold: float | None
    cannot_assess_reason: str | None = None


class ScoreBatchResponse(BaseModel):
    items: list[ScoreResponse]

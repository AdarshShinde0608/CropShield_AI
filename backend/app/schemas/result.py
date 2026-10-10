from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Risk = Literal["normal", "watch", "alert", "cannot_assess"]
Severity = Literal["moderate", "high"]
ConfidenceLabel = Literal["high", "medium", "low"]
RainContext = Literal["dry_spell", "normal", "not_applicable"]


class FieldResult(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "field_id": "F012",
                "risk": "alert",
                "severity": "moderate",
                "confidence": 0.62,
                "confidence_label": "medium",
                "z_score": -2.1,
                "pct_below_normal": 24.0,
                "drop_start": "2026-01-14",
                "latest_obs_date": "2026-02-08",
                "n_valid_obs": 3,
                "baseline_years": 6,
                "rain_context": "dry_spell",
                "advice_key": "advice.inspect_moisture",
                "advice": "Check soil moisture and irrigation status in this field.",
                "priority_score": 1.3,
                "priority_rank": 3,
                "if_flag": None,
                "is_synthetic": False,
            }
        },
    )

    field_id: str
    risk: Risk
    severity: Severity | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_label: ConfidenceLabel
    z_score: float | None = None
    pct_below_normal: float | None = None
    drop_start: date | None = None
    latest_obs_date: date | None = None
    n_valid_obs: int = Field(ge=0)
    baseline_years: int = Field(ge=0)
    rain_context: RainContext | None = None
    advice_key: str | None = None
    advice: str | None = None
    priority_score: float | None = None
    priority_rank: int | None = Field(default=None, ge=1)
    if_flag: bool | None = None
    is_synthetic: bool = False

    @model_validator(mode="after")
    def severity_only_for_alert(self) -> "FieldResult":
        if self.severity is not None and self.risk != "alert":
            raise ValueError("severity is only valid when risk is alert")
        return self
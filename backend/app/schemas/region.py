from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.result import ConfidenceLabel, Risk, Severity


class RegionOut(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "region_id": "region-01",
                "name": "Demo Region",
                "state": "Maharashtra",
                "latest_run_id": "run-2026-02-08-a",
                "latest_observation_date": "2026-02-08",
                "is_synthetic": True,
            }
        },
    )

    region_id: str
    name: str
    state: str | None = None
    latest_run_id: str | None = None
    latest_observation_date: date | None = None
    is_synthetic: bool | None = None


class RiskCounts(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"normal": 3, "watch": 1, "alert": 1, "cannot_assess": 0}
        },
    )

    normal: int = Field(default=0, ge=0)
    watch: int = Field(default=0, ge=0)
    alert: int = Field(default=0, ge=0)
    cannot_assess: int = Field(default=0, ge=0)


class RegionSummary(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "region_id": "region-01",
                "counts_by_risk": {
                    "normal": 3,
                    "watch": 1,
                    "alert": 1,
                    "cannot_assess": 0,
                },
                "latest_observation_date": "2026-02-08",
                "run_id": "run-2026-02-08-a",
                "is_synthetic": True,
            }
        },
    )

    region_id: str
    counts_by_risk: RiskCounts
    latest_observation_date: date | None = None
    run_id: str | None = None
    is_synthetic: bool | None = None


class QueueItem(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "field_id": "F012",
                "name": "Field 12",
                "risk": "alert",
                "severity": "moderate",
                "confidence_label": "medium",
                "latest_obs_date": "2026-02-08",
                "priority_rank": 3,
                "is_synthetic": True,
            }
        },
    )

    field_id: str
    name: str | None = None
    risk: Risk
    severity: Severity | None = None
    confidence_label: ConfidenceLabel
    latest_obs_date: date | None = None
    priority_rank: int | None = Field(default=None, ge=1)
    is_synthetic: bool = False


class MethodologyOut(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "run_id": "run-2026-02-08-a",
                "params": {"DOS_WINDOW": 12, "MIN_BASELINE_YEARS": 3},
                "method_steps": ["Clean and align observations", "Compare with baseline"],
                "validation_report": None,
                "limitations": ["NDVI does not identify the cause of an anomaly."],
                "created_at": "2026-02-08T10:00:00Z",
            }
        },
    )

    run_id: str | None = None
    params: dict[str, object] = Field(default_factory=dict)
    method_steps: list[str] = Field(default_factory=list)
    validation_report: dict[str, object] | None = None
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


RiskFilter = Risk | None
QueueSort = Literal["priority_rank"]

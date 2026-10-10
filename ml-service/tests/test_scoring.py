from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from packages.cropshield_core.features import MODEL_FEATURE_NAMES

from app.core.model import ModelRuntime
from app.core.config import Settings
from app.main import create_app
from app.schemas.scoring import ScoreRequest
from app.services.scorer import score_field


class _MetadataCollection:
    async def find_one(
        self,
        query: dict[str, str],
        projection: dict[str, int],
    ) -> dict[str, Any] | None:
        del query, projection
        return None


class _MetadataDatabase:
    model_artifacts = _MetadataCollection()


class _MetadataClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def __getitem__(self, name: str) -> _MetadataDatabase:
        del name
        return _MetadataDatabase()

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def use_fake_metadata_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.AsyncIOMotorClient", _MetadataClient)


class CalibratedStressEstimator:
    classes_ = np.asarray(["normal", "alert"])

    def predict(self, matrix: np.ndarray) -> np.ndarray:
        assert matrix.shape == (1, len(MODEL_FEATURE_NAMES))
        return np.asarray(["alert"])

    def predict_proba(self, matrix: np.ndarray) -> np.ndarray:
        assert matrix.shape == (1, len(MODEL_FEATURE_NAMES))
        return np.asarray([[0.2, 0.8]])

    def predict_with_explanations(self, matrix: np.ndarray) -> list[dict[str, Any]]:
        return [{"top_factors": {"NDVI": 0.2}}]


def _observation(day_offset: int) -> dict[str, Any]:
    observation_date = date.today() - timedelta(days=day_offset)
    indices = {
        "NDVI": 0.2,
        "NDWI": 0.12,
        "EVI": 0.34,
        "GNDVI": 0.42,
        "SAVI": 0.38,
    }
    return {
        "date": observation_date.isoformat(),
        "dos": 90 - day_offset,
        "ndvi": indices["NDVI"],
        "valid_frac": 0.82,
        "season": "Rabi",
        "low_quality": False,
        "is_interpolated": False,
        "indices": indices,
        "bands": {
            "Red": 0.11,
            "Green": 0.14,
            "Blue": 0.09,
            "NIR": 0.48,
            "SWIR": 0.23,
        },
        "rain_z": -1.2,
    }


def _request(**overrides: Any) -> ScoreRequest:
    values: dict[str, Any] = {
        "field_id": "field-1",
        "observations": [_observation(5), _observation(2)],
        "baseline_observations": [
            {"dos": 85, "baseline_median": 0.5, "baseline_sigma": 0.1},
            {"dos": 88, "baseline_median": 0.5, "baseline_sigma": 0.1},
        ],
    }
    values.update(overrides)
    return ScoreRequest.model_validate(values)


def _ready_model(task: str = "field-level crop-stress") -> ModelRuntime:
    return ModelRuntime(
        version="stress-v1",
        card={
            "task": task,
            "inference_artifact": "stress-model-mock",
            "input_specification": {"feature_names": list(MODEL_FEATURE_NAMES)},
            "risk_mapping": {
                "class_to_risk": {"normal": "normal", "alert": "alert"},
                "severity_by_risk": {"alert": "moderate"},
                "confidence": {
                    "source": "predict_proba",
                    "calibrated": True,
                    "cutoffs": {"medium": 0.5, "high": 0.75},
                },
                "decision_threshold": {
                    "score_class": "alert",
                    "minimum": 0.4,
                    "maximum": 0.9,
                    "default": 0.7,
                    "risk_on_met": "alert",
                    "risk_on_unmet": "watch",
                },
            },
        },
        artifacts={"stress-model-mock": CalibratedStressEstimator()},
        ready=True,
        error_code=None,
    )


def test_quality_gate_returns_cannot_assess_without_consulting_model() -> None:
    request = _request(observations=[_observation(2)])
    unavailable_model = ModelRuntime(None, None, {}, False, "MODEL_NOT_LOADED")

    result = score_field(request, unavailable_model)

    assert result.risk == "cannot_assess"
    assert result.cannot_assess_reason == "too_few_clear_observations"
    assert result.model_version is None
    assert result.model_score is None


def test_assessable_field_uses_verified_mapping_evidence_and_factors() -> None:
    result = score_field(_request(), _ready_model())

    assert result.risk == "alert"
    assert result.severity == "moderate"
    assert result.confidence == 0.8
    assert result.confidence_label == "high"
    assert result.model_score == 0.8
    assert result.model_version == "stress-v1"
    assert result.top_factors == {"NDVI": 0.2}
    assert result.drop_start == date.today() - timedelta(days=5)
    assert result.rain_context == "dry_spell"
    assert len(result.evidence.observations) == 2


def test_decision_threshold_override_is_clamped_to_card_range() -> None:
    low = score_field(_request(decision_threshold=0.1), _ready_model())
    high = score_field(_request(decision_threshold=0.95), _ready_model())

    assert low.decision_threshold == 0.4
    assert low.risk == "alert"
    assert high.decision_threshold == 0.9
    assert high.risk == "watch"
    assert high.severity is None


def test_crop_type_model_is_not_mapped_to_project_risk() -> None:
    with pytest.raises(HTTPException) as error:
        score_field(_request(), _ready_model(task="crop-type classification"))

    assert error.value.status_code == 503
    assert error.value.detail["code"] == "MODEL_MAPPING_UNSUPPORTED"


def test_schema_rejects_non_finite_and_unrecognized_input() -> None:
    payload = _request().model_dump(mode="json")
    payload["observations"][0]["ndvi"] = float("nan")
    with pytest.raises(ValidationError):
        ScoreRequest.model_validate(payload)

    payload = _request().model_dump(mode="json")
    payload["observations"][0]["unexpected"] = "value"
    with pytest.raises(ValidationError):
        ScoreRequest.model_validate(payload)


@pytest.mark.parametrize("value", ["2026-2-04", "2026-02-30", "2026-02-04T00:00:00"])
def test_schema_rejects_non_iso_or_invalid_dates(value: str) -> None:
    payload = _request().model_dump(mode="json")
    payload["observations"][0]["date"] = value

    with pytest.raises(ValidationError):
        ScoreRequest.model_validate(payload)


@pytest.mark.parametrize("value", [-1.01, 1.01])
def test_schema_rejects_ndvi_outside_physical_range(value: float) -> None:
    payload = _request().model_dump(mode="json")
    payload["observations"][0]["ndvi"] = value
    payload["observations"][0]["indices"]["NDVI"] = value

    with pytest.raises(ValidationError):
        ScoreRequest.model_validate(payload)


def test_http_score_can_return_cannot_assess_before_model_is_loaded(
    tmp_path: Path,
) -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        ML_SERVICE_API_KEY="local-test-service-key",
        MODEL_DIR=tmp_path,
    )
    application = create_app(settings)
    with TestClient(application) as client:
        response = client.post(
            "/v1/score",
            headers={"X-Service-Key": "local-test-service-key"},
            json={
                "field_id": "field-1",
                "observations": [_observation(2)],
            },
        )

    assert response.status_code == 200
    assert response.json()["risk"] == "cannot_assess"
    assert response.json()["model_version"] is None


def test_http_score_rejects_observation_count_over_limit(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        ML_SERVICE_API_KEY="local-test-service-key",
        MODEL_DIR=tmp_path,
        MAX_OBSERVATIONS_PER_FIELD=1,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/score",
            headers={"X-Service-Key": "local-test-service-key"},
            json=_request().model_dump(mode="json"),
        )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_http_batch_rejects_observation_count_over_limit(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        ML_SERVICE_API_KEY="local-test-service-key",
        MODEL_DIR=tmp_path,
        MAX_OBSERVATIONS_PER_FIELD=1,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/score/batch",
            headers={"X-Service-Key": "local-test-service-key"},
            json={"items": [_request().model_dump(mode="json")]},
        )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_http_score_requires_ready_model_after_quality_gate(
    tmp_path: Path,
) -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        ML_SERVICE_API_KEY="local-test-service-key",
        MODEL_DIR=tmp_path,
    )
    application = create_app(settings)
    with TestClient(application) as client:
        response = client.post(
            "/v1/score",
            headers={"X-Service-Key": "local-test-service-key"},
            json=_request().model_dump(mode="json"),
        )

    assert response.status_code == 503
    assert response.json()["code"] == "MODEL_NOT_LOADED"


@pytest.mark.parametrize(
    "path,body",
    [
        ("/v1/model-info", None),
        ("/v1/score", {"field_id": "field-1", "observations": [_observation(2)]}),
        (
            "/v1/score/batch",
            {"items": [{"field_id": "field-1", "observations": [_observation(2)]}]},
        ),
    ],
)
def test_all_v1_routes_require_service_key(
    tmp_path: Path,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        ML_SERVICE_API_KEY="local-test-service-key",
        MODEL_DIR=tmp_path,
    )
    application = create_app(settings)
    with TestClient(application) as client:
        response = client.get(path) if body is None else client.post(path, json=body)

    assert response.status_code == 401
    assert response.json()["code"] == "SERVICE_KEY_INVALID"


def test_batch_endpoint_rejects_more_than_configured_limit(
    tmp_path: Path,
) -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        ML_SERVICE_API_KEY="local-test-service-key",
        MODEL_DIR=tmp_path,
        MAX_BATCH_SIZE=1,
    )
    application = create_app(settings)
    with TestClient(application) as client:
        response = client.post(
            "/v1/score/batch",
            headers={"X-Service-Key": "local-test-service-key"},
            json={
                "items": [
                    {"field_id": "field-1", "observations": [_observation(2)]},
                    {"field_id": "field-2", "observations": [_observation(2)]},
                ]
            },
        )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"

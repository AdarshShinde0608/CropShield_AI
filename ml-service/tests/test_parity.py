from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from pipeline.score import score_current
from packages.cropshield_core.features import MODEL_FEATURE_NAMES

from app.core.config import Settings
from app.core.model import ModelRuntime
from app.main import create_app
from app.services.model_store import ModelStore

SCORE_TOLERANCE = 1e-6


class DeterministicStressEstimator:
    classes_ = np.asarray(["normal", "alert"])

    def predict(self, matrix: np.ndarray) -> np.ndarray:
        assert matrix.shape == (1, len(MODEL_FEATURE_NAMES))
        return np.asarray(["alert"])

    def predict_proba(self, matrix: np.ndarray) -> np.ndarray:
        assert matrix.shape == (1, len(MODEL_FEATURE_NAMES))
        return np.asarray([[0.2, 0.8]])


class MetadataCollection:
    async def find_one(
        self,
        query: dict[str, str],
        projection: dict[str, int],
    ) -> dict[str, Any]:
        del query, projection
        return {
            "model_version": "parity-test-only",
            "task": "field-level crop-stress",
            "status": "active",
            "measured_metrics": None,
        }


class MetadataDatabase:
    model_artifacts = MetadataCollection()


class MetadataClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def __getitem__(self, name: str) -> MetadataDatabase:
        del name
        return MetadataDatabase()

    def close(self) -> None:
        pass


def _fixture() -> tuple[list[dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    today = date.today()
    observations: list[dict[str, Any]] = []
    for offset, dos in ((5, 85), (2, 88)):
        observations.append(
            {
                "date": (today - timedelta(days=offset)).isoformat(),
                "dos": dos,
                "ndvi": 0.2,
                "valid_frac": 0.82,
                "season": "Rabi",
                "low_quality": False,
                "is_interpolated": False,
                "indices": {
                    "NDVI": 0.2,
                    "NDWI": 0.12,
                    "EVI": 0.34,
                    "GNDVI": 0.42,
                    "SAVI": 0.38,
                },
                "bands": {
                    "Red": 0.11,
                    "Green": 0.14,
                    "Blue": 0.09,
                    "NIR": 0.48,
                    "SWIR": 0.23,
                },
                "rain_z": -1.2,
                "baseline_median": 0.5,
                "baseline_sigma": 0.1,
            }
        )
    pipeline_observations = pd.DataFrame(
        [
            {
                "field_id": "parity-field",
                "date": item["date"],
                "dos": item["dos"],
                "ndvi": item["ndvi"],
                "valid_frac": item["valid_frac"],
                "low_quality": item["low_quality"],
                "is_interpolated": item["is_interpolated"],
            }
            for item in observations
        ]
    )
    baseline = pd.DataFrame(
        [
            {
                "field_id": "parity-field",
                "dos": item["dos"],
                "baseline_median": 0.5,
                "baseline_sigma": 0.1,
            }
            for item in observations
        ]
    )
    return observations, pipeline_observations, baseline


def test_pipeline_and_service_contract_parity_for_shared_fixture(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    observations, pipeline_observations, baseline = _fixture()
    _, pipeline_results = score_current(pipeline_observations, baseline)
    pipeline_result = pipeline_results[0]

    runtime = ModelRuntime(
        version="parity-test-only",
        card={
            "task": "field-level crop-stress",
            "inference_artifact": "test-double",
            "input_specification": {
                "feature_names": list(MODEL_FEATURE_NAMES),
            },
            "risk_mapping": {
                "class_to_risk": {"normal": "normal", "alert": "alert"},
                "severity_by_risk": {"alert": "high"},
                "confidence": {
                    "source": "predict_proba",
                    "calibrated": True,
                    "cutoffs": {"medium": 0.5, "high": 0.75},
                },
            },
        },
        artifacts={"test-double": DeterministicStressEstimator()},
        ready=True,
        error_code=None,
    )

    async def start_with_test_runtime(store: ModelStore) -> None:
        store._runtime = runtime
        store._readiness_error = None

    monkeypatch.setattr("app.main.AsyncIOMotorClient", MetadataClient)
    monkeypatch.setattr(ModelStore, "start", start_with_test_runtime)
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        ML_SERVICE_API_KEY="parity-test-key",
        MODEL_DIR=tmp_path,
    )
    request_body = {
        "field_id": "parity-field",
        "observations": [
            {key: value for key, value in item.items() if key not in {
                "baseline_median",
                "baseline_sigma",
            }}
            for item in observations
        ],
        "baseline_observations": [
            {
                "dos": item["dos"],
                "baseline_median": 0.5,
                "baseline_sigma": 0.1,
            }
            for item in observations
        ],
    }

    with TestClient(create_app(settings)) as client:
        ready_response = client.get("/ready")
        info_response = client.get(
            "/v1/model-info",
            headers={"X-Service-Key": "parity-test-key"},
        )
        response = client.post(
            "/v1/score",
            headers={"X-Service-Key": "parity-test-key"},
            json=request_body,
        )
        batch_response = client.post(
            "/v1/score/batch",
            headers={"X-Service-Key": "parity-test-key"},
            json={"items": [request_body]},
        )

    assert ready_response.status_code == 200
    assert info_response.status_code == 200
    assert info_response.json()["enabled"] is True
    assert response.status_code == 200
    assert batch_response.status_code == 200
    assert len(batch_response.json()["items"]) == 1
    service_result = response.json()
    assert pipeline_result["risk"] == service_result["risk"] == "alert"
    assert pipeline_result["severity"] == service_result["severity"] == "high"
    assert pipeline_result["drop_start"].isoformat() == service_result["drop_start"]
    assert service_result["model_score"] == pytest.approx(0.8, abs=SCORE_TOLERANCE)

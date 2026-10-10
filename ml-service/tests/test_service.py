import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.model import load_model
from app.main import create_app


class _MetadataCollection:
    async def find_one(
        self,
        query: dict[str, str],
        projection: dict[str, int],
    ) -> dict[str, Any] | None:
        assert query == {"status": "active"}
        assert projection == {
            "_id": 0,
            "model_version": 1,
            "artifact_checksums": 1,
            "weights_stored": 1,
        }
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


class _MismatchedMetadataCollection:
    async def find_one(
        self,
        query: dict[str, str],
        projection: dict[str, int],
    ) -> dict[str, Any]:
        del query, projection
        return {
            "model_version": "missing-model",
            "artifact_checksums": {"model.onnx": "a" * 64},
            "weights_stored": False,
        }


class _MismatchedMetadataDatabase:
    model_artifacts = _MismatchedMetadataCollection()


class _MismatchedMetadataClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def __getitem__(self, name: str) -> _MismatchedMetadataDatabase:
        del name
        return _MismatchedMetadataDatabase()

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def use_fake_metadata_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.AsyncIOMotorClient", _MetadataClient)


def _settings(model_dir: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "APP_ENV": "development",
        "ML_SERVICE_API_KEY": "local-test-service-key",
        "MODEL_DIR": model_dir,
    }
    values.update(overrides)
    return Settings(**values)


def test_health_is_live_and_request_id_is_returned(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.get("/health", headers={"X-Request-ID": "pipeline-test-01"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "pipeline-test-01"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Content-Security-Policy"] == "default-src 'none'"
    assert response.headers["Cache-Control"] == "no-store"


def test_oversized_declared_body_returns_contract_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path, MAX_REQUEST_BYTES=16)
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/score", content=b"x" * 17)

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_oversized_chunked_body_without_content_length_is_rejected(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, MAX_REQUEST_BYTES=16)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/score",
            content=iter([b"x" * 10, b"x" * 10]),
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_request_timeout_returns_gateway_timeout_error(tmp_path: Path) -> None:
    import asyncio

    application = create_app(_settings(tmp_path, REQUEST_TIMEOUT_SECONDS=0.01))

    async def slow_route() -> dict[str, str]:
        await asyncio.sleep(0.05)
        return {"status": "late"}

    application.add_api_route("/slow", slow_route)
    with TestClient(application) as client:
        response = client.get("/slow")

    assert response.status_code == 504
    assert response.json()["code"] == "REQUEST_TIMEOUT"


def test_rate_limit_is_shared_by_key_across_client_ips(tmp_path: Path) -> None:
    application = create_app(
        _settings(tmp_path, RATE_LIMIT_REQUESTS_PER_MINUTE=1)
    )
    with TestClient(application, client=("10.0.0.1", 1001)) as first_client:
        first = first_client.get(
            "/v1/model-info",
            headers={"X-Service-Key": "caller-one"},
        )
    with TestClient(application, client=("10.0.0.2", 1002)) as second_client:
        second = second_client.get(
            "/v1/model-info",
            headers={"X-Service-Key": "caller-one"},
        )

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.json()["code"] == "RATE_LIMITED"


def test_rate_limit_is_shared_by_ip_across_keys(tmp_path: Path) -> None:
    application = create_app(
        _settings(tmp_path, RATE_LIMIT_REQUESTS_PER_MINUTE=1)
    )
    with TestClient(application, client=("10.0.0.1", 1001)) as client:
        first = client.get("/v1/model-info", headers={"X-Service-Key": "caller-one"})
        second = client.get("/v1/model-info", headers={"X-Service-Key": "caller-two"})

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.json()["code"] == "RATE_LIMITED"


def test_ready_is_unavailable_until_a_verified_model_is_loaded(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The verified model is not ready",
        "code": "MODEL_NOT_LOADED",
    }


def test_ready_reports_checksum_mismatch_from_active_model_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.main.AsyncIOMotorClient", _MismatchedMetadataClient)

    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The verified model is not ready",
        "code": "MODEL_MISMATCH",
    }


@pytest.mark.parametrize("headers", [{}, {"X-Service-Key": "wrong"}])
def test_model_info_requires_a_valid_service_key(
    tmp_path: Path, headers: dict[str, str]
) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.get("/v1/model-info", headers=headers)

    assert response.status_code == 401
    assert response.json() == {
        "detail": "A valid service key is required",
        "code": "SERVICE_KEY_INVALID",
    }


def test_previous_service_key_is_accepted_during_rotation(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        ML_SERVICE_API_KEY="current-development-key",
        ML_SERVICE_API_KEY_PREVIOUS="next-development-key",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/v1/model-info",
            headers={"X-Service-Key": "next-development-key"},
        )

    assert response.status_code != 401


def test_production_requires_long_key_and_disables_openapi(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="ML_SERVICE_API_KEY"):
        _settings(tmp_path, APP_ENV="production", ML_SERVICE_API_KEY="short")
    with pytest.raises(ValidationError, match="repository-root"):
        _settings(
            tmp_path,
            APP_ENV="production",
            ML_SERVICE_API_KEY="x" * 32,
        )

    settings = _settings(
        tmp_path,
        APP_ENV="production",
        ML_SERVICE_API_KEY="x" * 32,
        MODEL_DIR=Path("models"),
    )
    application = create_app(settings)
    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None


@pytest.mark.parametrize("artifact_name", ["estimator.joblib", "model.onnx"])
def test_model_loader_fails_closed_without_deserializing_artifacts(
    tmp_path: Path,
    artifact_name: str,
) -> None:
    artifact_path = tmp_path / artifact_name
    artifact_path.write_bytes(b"opaque model fixture")
    checksum = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    (tmp_path / "model_card.json").write_text(
        json.dumps(
            {
                "version": "test-v1",
                "artifact_files": [artifact_name],
                "artifact_checksums": {artifact_name: checksum},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_model(tmp_path)
    assert loaded.ready is False
    assert loaded.version == "test-v1"
    assert loaded.error_code == "MODEL_FORMAT_UNSUPPORTED"
    assert loaded.artifacts == {}


def test_rate_limit_returns_contract_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path, RATE_LIMIT_REQUESTS_PER_MINUTE=1)
    with TestClient(create_app(settings)) as client:
        first = client.get("/v1/model-info")
        second = client.get("/v1/model-info")
        health = client.get("/health")

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.json()["code"] == "RATE_LIMITED"
    assert health.status_code == 200

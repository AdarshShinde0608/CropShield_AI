from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio

from app.core.rate_limit import LoginRateLimiter
from app.main import app
from app.services.ml_client import MLServiceClient, MLServiceError

SERVICE_KEY = "backend-to-ml-test-key"
FIELD_IDS = [f"F00{number}" for number in range(1, 6)]
REGION_ID = "region-01"
SEASON_ID = "2025-26"


def _ml_response(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/ready":
        return httpx.Response(200, json={"status": "ready", "model_version": "test-v1"})
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    if request.url.path == "/v1/model-info":
        return httpx.Response(
            200,
            json={
                "model_version": "test-v1",
                "risk_mapping": {
                    "decision_threshold": {
                        "minimum": 0.1,
                        "maximum": 0.9,
                        "default": 0.5,
                    }
                },
            },
        )
    if request.url.path == "/v1/score":
        return httpx.Response(
            200,
            json={
                "field_id": "F001",
                "risk": "watch",
                "severity": None,
                "confidence": 0.7,
                "confidence_label": "medium",
                "model_score": 0.7,
                "model_version": "test-v1",
                "preview": False,
            },
        )
    if request.url.path == "/v1/score/batch":
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "field_id": item["field_id"],
                        "risk": "watch",
                    }
                    for item in payload["items"]
                ]
            },
        )
    return httpx.Response(404, json={"detail": "not found"})


@pytest_asyncio.fixture
async def ml_client() -> Any:
    received: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return _ml_response(request)

    transport = httpx.MockTransport(handler)
    upstream = httpx.AsyncClient(transport=transport)
    previous_client = getattr(app.state, "ml_service_client", None)
    app.state.ml_service_client = MLServiceClient(
        "https://ml.test",
        SERVICE_KEY,
        client=upstream,
    )
    app.state.ml_warmup_rate_limiter = LoginRateLimiter()
    try:
        yield received
    finally:
        app.state.ml_service_client = previous_client
        await upstream.aclose()


def _observation_doc(field_id: str, offset: int) -> dict[str, Any]:
    observed_date = date.today() - timedelta(days=offset)
    indices = {"NDVI": 0.5, "NDWI": 0.1, "EVI": 0.3, "GNDVI": 0.4, "SAVI": 0.35}
    return {
        "field_id": field_id,
        "season_id": SEASON_ID,
        "date": observed_date.isoformat(),
        "dos": 80 - offset,
        "ndvi": 0.5,
        "valid_frac": 0.9,
        "low_quality": False,
        "is_interpolated": False,
        "indices": indices,
        "bands": {"Red": 0.1, "Green": 0.12, "Blue": 0.08, "NIR": 0.5, "SWIR": 0.2},
        "baseline_median": 0.6,
        "baseline_sigma": 0.1,
    }


async def _insert_model_inputs(database: Any, field_ids: list[str]) -> None:
    for field_id in field_ids:
        await database.observations.delete_many(
            {"field_id": field_id, "season_id": SEASON_ID}
        )
        await database.observations.insert_many(
            [_observation_doc(field_id, 4), _observation_doc(field_id, 1)]
        )


@pytest.mark.asyncio
async def test_ml_client_propagates_request_id_and_service_key(
    ml_client: Any,
    shared_client: httpx.AsyncClient,
) -> None:
    response = await shared_client.get(
        "/api/model-info",
        headers={"X-Request-ID": "request-123"},
    )

    assert response.status_code == 200
    received_request = next(
        request for request in ml_client if request.url.path == "/v1/model-info"
    )
    assert received_request.headers["X-Service-Key"] == SERVICE_KEY
    assert received_request.headers["X-Request-ID"] == "request-123"


@pytest.mark.asyncio
async def test_ml_client_maps_connect_failure_and_opens_circuit_after_three_failures() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("connection refused", request=request)

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = MLServiceClient("https://ml.test", SERVICE_KEY, client=upstream)
    try:
        for _ in range(3):
            with pytest.raises(MLServiceError) as error:
                await client.ready()
            assert error.value.code == "ML_WAKING"
        calls_after_retries = calls
        with pytest.raises(MLServiceError) as open_error:
            await client.ready()
        assert open_error.value.code == "ML_UNAVAILABLE"
        assert calls == calls_after_retries == 6
    finally:
        await upstream.aclose()


@pytest.mark.asyncio
async def test_ml_client_maps_timeout_to_waking() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = MLServiceClient("https://ml.test", SERVICE_KEY, client=upstream)
    try:
        with pytest.raises(MLServiceError) as error:
            await client.ready()
    finally:
        await upstream.aclose()

    assert error.value.code == "ML_WAKING"


@pytest.mark.asyncio
async def test_wrong_service_key_maps_to_unavailable() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Service-Key"] == "wrong-key"
        return httpx.Response(401, json={"code": "SERVICE_KEY_INVALID"})

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = MLServiceClient("https://ml.test", "wrong-key", client=upstream)
    try:
        with pytest.raises(MLServiceError) as error:
            await client.model_info()
    finally:
        await upstream.aclose()

    assert error.value.code == "ML_UNAVAILABLE"


@pytest.mark.asyncio
async def test_status_and_warmup_routes(ml_client: Any, shared_client: httpx.AsyncClient) -> None:
    status_response = await shared_client.get("/api/ml/status")
    warmup_response = await shared_client.post("/api/ml/warmup")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "ready"
    assert warmup_response.status_code == 202
    assert warmup_response.json() == {"status": "accepted"}


@pytest.mark.asyncio
async def test_optional_ml_can_be_disabled_without_upstream_requests(
    ml_client: Any,
    shared_client: httpx.AsyncClient,
) -> None:
    old_client = app.state.ml_service_client
    app.state.ml_service_client = None
    try:
        status_response = await shared_client.get("/api/ml/status")
        warmup_response = await shared_client.post("/api/ml/warmup")
        model_info_response = await shared_client.get("/api/model-info")
    finally:
        app.state.ml_service_client = old_client

    assert status_response.status_code == 503
    assert status_response.json()["code"] == "ML_UNAVAILABLE"
    assert warmup_response.status_code == 202
    assert warmup_response.json() == {"status": "disabled"}
    assert model_info_response.status_code == 503
    assert model_info_response.json()["code"] == "ML_UNAVAILABLE"


@pytest.mark.asyncio
async def test_warmup_is_rate_limited(ml_client: Any, shared_client: httpx.AsyncClient) -> None:
    app.state.ml_warmup_rate_limiter = LoginRateLimiter(max_attempts=1)
    first = await shared_client.post("/api/ml/warmup")
    second = await shared_client.post("/api/ml/warmup")

    assert first.status_code == 202
    assert second.status_code == 429
    assert second.json()["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_model_info_uses_database_fallback_when_service_is_waking(
    ml_client: Any,
    shared_database: Any,
    shared_client: httpx.AsyncClient,
) -> None:
    await shared_database.model_artifacts.insert_one(
        {
            "model_version": "db-v1",
            "status": "active",
            "task": "field-level crop-stress",
        }
    )

    async def waking(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sleeping", request=request)

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(waking))
    old_client = app.state.ml_service_client
    app.state.ml_service_client = MLServiceClient(
        "https://ml.test",
        SERVICE_KEY,
        client=upstream,
    )
    try:
        response = await shared_client.get("/api/model-info")
    finally:
        app.state.ml_service_client = old_client
        await upstream.aclose()

    assert response.status_code == 200
    assert response.json()["model_version"] == "db-v1"
    assert response.json()["source"] == "database"
    assert response.json()["enabled"] is False


@pytest.mark.asyncio
async def test_field_preview_sends_current_observations_and_saves_nothing(
    ml_client: Any,
    shared_database: Any,
    shared_client: httpx.AsyncClient,
) -> None:
    await _insert_model_inputs(shared_database, [FIELD_IDS[0]])
    initial_results = await shared_database.field_results.count_documents({})

    response = await shared_client.post(
        f"/api/fields/{FIELD_IDS[0]}/score-preview",
        headers={"X-Request-ID": "field-preview-1"},
    )

    assert response.status_code == 200
    assert response.json()["preview"] is True
    assert response.json()["field_id"] == FIELD_IDS[0]
    assert await shared_database.field_results.count_documents({}) == initial_results


@pytest.mark.asyncio
async def test_field_preview_rejects_threshold_when_model_card_disallows_it(
    ml_client: Any,
    shared_database: Any,
    shared_client: httpx.AsyncClient,
) -> None:
    await _insert_model_inputs(shared_database, [FIELD_IDS[0]])

    async def no_threshold(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/model-info":
            return httpx.Response(200, json={"model_version": "test-v1"})
        return _ml_response(request)

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(no_threshold))
    old_client = app.state.ml_service_client
    app.state.ml_service_client = MLServiceClient(
        "https://ml.test",
        SERVICE_KEY,
        client=upstream,
    )
    try:
        response = await shared_client.post(
            f"/api/fields/{FIELD_IDS[0]}/score-preview",
            json={"decision_threshold": 0.7},
        )
    finally:
        app.state.ml_service_client = old_client
        await upstream.aclose()

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_preview_fails_explicitly_when_required_spectral_inputs_are_absent(
    ml_client: Any,
    shared_client: httpx.AsyncClient,
) -> None:
    response = await shared_client.post("/api/fields/F001/score-preview")

    assert response.status_code == 422
    assert response.json()["code"] == "ML_INPUT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_region_preview_batches_and_counts_risks(
    ml_client: Any,
    shared_database: Any,
    shared_client: httpx.AsyncClient,
) -> None:
    await _insert_model_inputs(shared_database, FIELD_IDS)

    response = await shared_client.post(
        f"/api/regions/{REGION_ID}/score-preview",
    )

    assert response.status_code == 200
    assert response.json() == {
        "region_id": REGION_ID,
        "preview": True,
        "total_fields": 5,
        "scored_fields": 5,
        "counts_by_risk": {
            "normal": 0,
            "watch": 5,
            "alert": 0,
            "cannot_assess": 0,
        },
    }


@pytest.mark.asyncio
async def test_api_reports_wrong_service_key_as_unavailable(
    ml_client: Any,
    shared_client: httpx.AsyncClient,
) -> None:
    async def unauthorized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": "SERVICE_KEY_INVALID"})

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(unauthorized))
    old_client = app.state.ml_service_client
    app.state.ml_service_client = MLServiceClient(
        "https://ml.test",
        SERVICE_KEY,
        client=upstream,
    )
    try:
        response = await shared_client.get("/api/ml/status")
    finally:
        app.state.ml_service_client = old_client
        await upstream.aclose()

    assert response.status_code == 503
    assert response.json()["code"] == "ML_UNAVAILABLE"

import logging

import httpx
import pytest

from app.core.rate_limit import LoginRateLimiter
from app.main import app


@pytest.mark.asyncio
async def test_login_is_limited_to_five_attempts_per_minute(
    anonymous_client: httpx.AsyncClient,
) -> None:
    app.state.login_rate_limiter = LoginRateLimiter()
    responses = [
        await anonymous_client.post(
            "/api/auth/login",
            json={"email": "unknown@example.org", "password": "not-a-real-password"},
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [401] * 5 + [429]
    assert responses[-1].json()["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_request_logs_have_metadata_but_not_request_body(
    anonymous_client: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    app.state.login_rate_limiter = LoginRateLimiter()
    secret = "request-body-secret-value"
    with caplog.at_level(logging.INFO, logger="cropshield.request"):
        await anonymous_client.post(
            "/api/auth/login",
            json={"email": "unknown@example.org", "password": secret},
        )

    log_records = [
        record for record in caplog.records if record.name == "cropshield.request"
    ]
    assert log_records
    record = log_records[-1]
    assert record.method == "POST"
    assert record.path == "/api/auth/login"
    assert record.status_code == 401
    assert record.duration_ms >= 0
    assert secret not in record.getMessage()


def test_openapi_includes_all_api_tags() -> None:
    schema = app.openapi()
    tag_names = {tag["name"] for tag in schema["tags"]}

    assert {
        "health",
        "auth",
        "regions",
        "fields",
        "actions",
        "methodology",
    } <= tag_names


@pytest.mark.asyncio
async def test_api_responses_never_expose_internal_database_or_password_fields(
    shared_client: httpx.AsyncClient,
    anonymous_client: httpx.AsyncClient,
) -> None:
    responses = [
        await shared_client.get("/api/auth/me"),
        await shared_client.get("/api/regions"),
        await shared_client.get("/api/regions/region-01/summary"),
        await shared_client.get("/api/regions/region-01/fields"),
        await shared_client.get("/api/regions/region-01/queue"),
        await shared_client.get("/api/fields/F001"),
        await shared_client.get("/api/fields/F001/timeseries"),
        await shared_client.get("/api/fields/F001/actions"),
        await anonymous_client.get("/api/methodology"),
    ]
    created = await shared_client.post(
        "/api/fields/F001/actions",
        json={"status": "pending"},
    )
    responses.append(created)
    updated = await shared_client.patch(
        f"/api/actions/{created.json()['id']}",
        json={"status": "done"},
    )
    responses.append(updated)

    assert all(response.status_code in {200, 201} for response in responses)

    def check_public_value(value: object) -> None:
        if isinstance(value, dict):
            assert "_id" not in value
            assert "password_hash" not in value
            for nested in value.values():
                check_public_value(nested)
        elif isinstance(value, list):
            for nested in value:
                check_public_value(nested)

    for response in responses:
        check_public_value(response.json())

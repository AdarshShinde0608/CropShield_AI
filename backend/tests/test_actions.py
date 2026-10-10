from typing import Any

import httpx
import pytest
from bson import ObjectId

from app.core.security import create_access_token
from app.main import app

FIELD_ID = "F001"
TEST_USER_ID = "65b2f4c8d4a19f0271b2c3d4"


@pytest.mark.asyncio
async def test_create_and_list_actions_for_owned_field(
    shared_client: httpx.AsyncClient,
) -> None:
    created = await shared_client.post(
        f"/api/fields/{FIELD_ID}/actions",
        json={"status": "pending", "note": "Inspect the field boundary."},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["user_id"] == TEST_USER_ID
    assert body["field_id"] == FIELD_ID
    assert body["status"] == "pending"
    assert "password_hash" not in body
    assert "_id" not in body

    listed = await shared_client.get(f"/api/fields/{FIELD_ID}/actions")
    assert listed.status_code == 200
    assert [action["id"] for action in listed.json()] == [body["id"]]


@pytest.mark.asyncio
async def test_patch_action_updates_status_and_note(
    shared_client: httpx.AsyncClient,
) -> None:
    created = await shared_client.post(
        f"/api/fields/{FIELD_ID}/actions",
        json={"status": "pending"},
    )

    response = await shared_client.patch(
        f"/api/actions/{created.json()['id']}",
        json={"status": "done", "note": "Inspection recorded."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert response.json()["note"] == "Inspection recorded."
    assert response.json()["updated_at"] >= response.json()["created_at"]


@pytest.mark.asyncio
async def test_action_update_rejects_another_users_action(
    shared_client: httpx.AsyncClient,
    shared_database: Any,
) -> None:
    created = await shared_client.post(
        f"/api/fields/{FIELD_ID}/actions",
        json={"status": "pending"},
    )
    other_user_id = "65b2f4c8d4a19f0271b2c3e5"
    await shared_database.users.insert_one(
        {
            "_id": ObjectId(other_user_id),
            "email": "other@example.org",
            "password_hash": "not-returned",
            "name": "Other User",
            "role": "officer",
            "language": "en",
        }
    )
    other_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {create_access_token(other_user_id, 'officer')}"
        },
    )
    try:
        response = await other_client.patch(
            f"/api/actions/{created.json()['id']}",
            json={"status": "done"},
        )
    finally:
        await other_client.aclose()

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_action_list_only_returns_current_users_records(
    shared_client: httpx.AsyncClient,
    shared_database: Any,
) -> None:
    await shared_database.actions.insert_one(
        {
            "action_id": "belongs-to-someone-else",
            "user_id": "another-user",
            "field_id": FIELD_ID,
            "status": "pending",
            "note": "Private inspection note.",
        }
    )
    created = await shared_client.post(
        f"/api/fields/{FIELD_ID}/actions",
        json={"status": "pending"},
    )

    response = await shared_client.get(f"/api/fields/{FIELD_ID}/actions")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [created.json()["id"]]


@pytest.mark.asyncio
async def test_action_routes_return_not_found_for_unknown_ids(
    shared_client: httpx.AsyncClient,
) -> None:
    unknown_field = await shared_client.get("/api/fields/unknown/actions")
    unknown_action = await shared_client.patch(
        "/api/actions/unknown",
        json={"status": "done"},
    )

    assert unknown_field.status_code == 404
    assert unknown_field.json()["code"] == "NOT_FOUND"
    assert unknown_action.status_code == 404
    assert unknown_action.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_action_routes_require_authentication(
    anonymous_client: httpx.AsyncClient,
) -> None:
    responses = [
        await anonymous_client.get(f"/api/fields/{FIELD_ID}/actions"),
        await anonymous_client.post(
            f"/api/fields/{FIELD_ID}/actions",
            json={"status": "pending"},
        ),
        await anonymous_client.patch(
            "/api/actions/action-id",
            json={"status": "done"},
        ),
    ]

    assert [response.status_code for response in responses] == [401, 401, 401]
    assert all(response.json()["code"] == "TOKEN_INVALID" for response in responses)


@pytest.mark.asyncio
async def test_action_note_limit_is_validated(
    shared_client: httpx.AsyncClient,
) -> None:
    response = await shared_client.post(
        f"/api/fields/{FIELD_ID}/actions",
        json={"status": "pending", "note": "x" * 501},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_action_status_cannot_be_cleared_to_null(
    shared_client: httpx.AsyncClient,
) -> None:
    created = await shared_client.post(
        f"/api/fields/{FIELD_ID}/actions",
        json={"status": "pending"},
    )

    response = await shared_client.patch(
        f"/api/actions/{created.json()['id']}",
        json={"status": None, "note": "Keep the valid status."},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_methodology_is_public_and_does_not_fabricate_validation(
    anonymous_client: httpx.AsyncClient,
) -> None:
    response = await anonymous_client.get("/api/methodology")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run-seeded"
    assert body["params"] == {"baseline_years": 5, "index": "NDVI"}
    assert body["validation_report"] is None
    assert len(body["method_steps"]) == 10
    assert body["limitations"]
    assert "_id" not in body


@pytest.mark.asyncio
async def test_methodology_returns_validation_report_for_latest_run(
    anonymous_client: httpx.AsyncClient,
    shared_database: Any,
) -> None:
    await shared_database.validation_reports.insert_one(
        {
            "run_id": "run-seeded",
            "metrics": {"tested_fields": 8, "false_alert_rate": 0.1},
        }
    )

    response = await anonymous_client.get("/api/methodology")

    assert response.status_code == 200
    assert response.json()["validation_report"] == {
        "metrics": {"tested_fields": 8, "false_alert_rate": 0.1}
    }


@pytest.mark.asyncio
async def test_methodology_works_without_an_analysis_run(
    anonymous_client: httpx.AsyncClient,
    shared_database: Any,
) -> None:
    await shared_database.analysis_runs.delete_many({})

    response = await anonymous_client.get("/api/methodology")

    assert response.status_code == 200
    assert response.json()["run_id"] is None
    assert response.json()["validation_report"] is None
    assert response.json()["params"] == {}
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app

TEST_USER_ID = "65b2f4c8d4a19f0271b2c3d4"
TEST_EMAIL = "shared-test@example.org"
TEST_PASSWORD = "test-password-123"
REGION_ID = "region-01"
SEASON_ID = "2025-26"
RUN_ID = "run-seeded"
FIELD_IDS = [f"F00{number}" for number in range(1, 6)]
GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[73.0, 19.0], [73.1, 19.0], [73.1, 19.1], [73.0, 19.0]]],
}


@pytest_asyncio.fixture
async def shared_database() -> AsyncIterator[Any]:
    client = AsyncMongoMockClient()
    database_name = f"cropshield_shared_test_{uuid4().hex}"
    database = client[database_name]
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: database
    await database.users.insert_one(
        {
            "_id": ObjectId(TEST_USER_ID),
            "email": TEST_EMAIL,
            "password_hash": hash_password(TEST_PASSWORD),
            "name": "Test Officer",
            "role": "officer",
            "language": "en",
        }
    )
    await database.regions.insert_one(
        {"region_id": REGION_ID, "name": "Seeded Region", "state": "Maharashtra"}
    )
    await database.seasons.insert_one(
        {"season_id": SEASON_ID, "role": "current", "label": "2025-26"}
    )
    await database.analysis_runs.insert_one(
        {
            "run_id": RUN_ID,
            "created_at": datetime(2026, 2, 8, tzinfo=timezone.utc),
            "params": {"baseline_years": 5, "index": "NDVI"},
            "is_synthetic": True,
        }
    )
    for number, field_id in enumerate(FIELD_IDS, start=1):
        await database.fields.insert_one(
            {
                "field_id": field_id,
                "region_id": REGION_ID,
                "name": f"Seeded Field {number}",
                "geometry": GEOMETRY,
                "is_synthetic_boundary": True,
            }
        )
        await database.field_results.insert_one(
            {
                "field_id": field_id,
                "region_id": REGION_ID,
                "season_id": SEASON_ID,
                "run_id": RUN_ID,
                "risk": "alert" if number == 1 else "watch",
                "severity": "moderate" if number == 1 else None,
                "confidence": 0.7,
                "confidence_label": "medium",
                "latest_obs_date": "2026-02-08",
                "priority_rank": number,
                "n_valid_obs": 4,
                "baseline_years": 5,
                "is_synthetic": True,
            }
        )
        await database.observations.insert_many(
            [
                {
                    "field_id": field_id,
                    "season_id": SEASON_ID,
                    "date": "2026-01-04",
                    "ndvi": 0.5,
                    "baseline_median": 0.6,
                    "baseline_sigma": 0.1,
                },
                {
                    "field_id": field_id,
                    "season_id": SEASON_ID,
                    "date": "2026-02-08",
                    "ndvi": 0.4,
                    "baseline_median": 0.6,
                    "baseline_sigma": 0.1,
                },
            ]
        )
    await database.rainfall.insert_one(
        {
            "region_id": REGION_ID,
            "date": "2026-01-20",
            "rain_mm": 4.0,
            "rain14": 10.0,
            "rain30": 24.0,
        }
    )
    try:
        yield database
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        await client.drop_database(database_name)
        client.close()


@pytest_asyncio.fixture
async def mongodb_test_database() -> AsyncIterator[Any]:
    test_uri = os.environ.get("MONGODB_TEST_URI", "").strip()
    if not test_uri:
        pytest.skip("MONGODB_TEST_URI is unset; skipping real MongoDB test")
    configured_uri = os.environ.get("MONGODB_URI", "").strip()
    if configured_uri and test_uri == configured_uri:
        pytest.fail("MONGODB_TEST_URI must be separate from MONGODB_URI")

    client = AsyncIOMotorClient(test_uri, serverSelectionTimeoutMS=5000)
    database_name = f"cropshield_test_{uuid4().hex}"
    try:
        await client.admin.command("ping")
    except Exception:
        client.close()
        raise

    try:
        yield client[database_name]
    finally:
        await client.drop_database(database_name)
        client.close()


@pytest_asyncio.fixture
async def shared_client(shared_database: Any) -> AsyncIterator[httpx.AsyncClient]:
    del shared_database
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {create_access_token(TEST_USER_ID, 'officer')}"
        },
    ) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def anonymous_client(shared_database: Any) -> AsyncIterator[httpx.AsyncClient]:
    del shared_database
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
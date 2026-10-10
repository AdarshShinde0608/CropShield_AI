from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app

REGION_ID = "region-01"
FIELD_ID = "F001"
SEASON_ID = "2025-26"
RUN_ID = "run-current"
TEST_USER_ID = "65b2f4c8d4a19f0271b2c3d4"
GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[73.0, 19.0], [73.1, 19.0], [73.1, 19.1], [73.0, 19.0]]],
}


@pytest_asyncio.fixture
async def database() -> AsyncIterator[Any]:
    client = AsyncMongoMockClient()
    database_name = f"cropshield_regions_test_{uuid4().hex}"
    test_database = client[database_name]
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: test_database
    user_id = ObjectId(TEST_USER_ID)
    await test_database.users.insert_one(
        {
            "_id": user_id,
            "email": "regions-test@example.org",
            "password_hash": hash_password("test-password"),
            "name": "Test Officer",
            "role": "officer",
            "language": "en",
        }
    )
    try:
        yield test_database
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        await client.drop_database(database_name)
        client.close()


@pytest_asyncio.fixture
async def client(database: Any) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "Authorization": (
                "Bearer "
                + create_access_token(TEST_USER_ID, "officer")
            )
        },
    ) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def seeded_database(database: Any) -> Any:
    await database.regions.insert_one(
        {
            "region_id": REGION_ID,
            "name": "Demo Region",
            "state": "Maharashtra",
            "bbox": [73.0, 19.0, 73.1, 19.1],
        }
    )
    await database.seasons.insert_one(
        {"season_id": SEASON_ID, "role": "current", "label": "2025-26"}
    )
    await database.analysis_runs.insert_one(
        {
            "run_id": RUN_ID,
            "created_at": datetime(2026, 2, 8, tzinfo=timezone.utc),
            "params": {"DOS_WINDOW": 12},
            "is_synthetic": True,
        }
    )
    for field_id, name, rank in [
        ("F001", "First Field", 2),
        ("F002", "Second Field", 1),
    ]:
        await database.fields.insert_one(
            {
                "field_id": field_id,
                "region_id": REGION_ID,
                "name": name,
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
                "risk": "alert" if field_id == "F001" else "watch",
                "severity": "moderate" if field_id == "F001" else None,
                "confidence": 0.7,
                "confidence_label": "medium",
                "z_score": -2.1,
                "pct_below_normal": 24.0,
                "drop_start": "2026-01-14",
                "latest_obs_date": "2026-02-08",
                "n_valid_obs": 3,
                "baseline_years": 6,
                "rain_context": "dry_spell",
                "advice_key": "advice.inspect_moisture",
                "advice": "Check soil moisture and irrigation status.",
                "priority_score": 1.2,
                "priority_rank": rank,
            }
        )
    await database.observations.insert_many(
        [
            {
                "field_id": FIELD_ID,
                "season_id": SEASON_ID,
                "date": "2026-01-04",
                "ndvi": 0.51,
                "baseline_median": 0.58,
                "baseline_sigma": 0.06,
                "z": -0.9,
                "low_quality": False,
                "is_interpolated": False,
            },
            {
                "field_id": FIELD_ID,
                "season_id": SEASON_ID,
                "date": "2026-02-08",
                "ndvi": 0.4,
                "baseline_median": 0.6,
                "baseline_sigma": 0.1,
                "z": -2.0,
                "low_quality": True,
                "is_interpolated": False,
            },
            {
                "field_id": FIELD_ID,
                "season_id": "2019-20",
                "date": "2020-01-04",
                "ndvi": 0.7,
            },
        ]
    )
    await database.rainfall.insert_many(
        [
            {"region_id": REGION_ID, "date": "2026-01-04", "rain_mm": 0.0, "rain30": 4.2},
            {"region_id": REGION_ID, "date": "2026-02-08", "rain_mm": 1.0, "rain30": 9.0},
            {"region_id": REGION_ID, "date": "2026-03-01", "rain_mm": 2.0},
        ]
    )
    return database


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/regions",
        "/api/regions/region-01/summary",
        "/api/regions/region-01/fields",
        "/api/regions/region-01/queue",
        "/api/fields/F001",
        "/api/fields/F001/timeseries",
    ],
)
async def test_region_and_field_routes_require_auth(database: Any, path: str) -> None:
    del database
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        response = await test_client.get(path)

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


@pytest.mark.asyncio
async def test_list_regions_includes_latest_run(seeded_database: Any, client: httpx.AsyncClient) -> None:
    response = await client.get("/api/regions")

    assert response.status_code == 200
    assert response.json()[0]["region_id"] == REGION_ID
    assert response.json()[0]["latest_run_id"] == RUN_ID
    assert response.json()[0]["is_synthetic"] is True


@pytest.mark.asyncio
async def test_region_summary_counts_results_and_synthetic_run(
    seeded_database: Any,
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"/api/regions/{REGION_ID}/summary")

    assert response.status_code == 200
    assert response.json()["counts_by_risk"] == {
        "normal": 0,
        "watch": 1,
        "alert": 1,
        "cannot_assess": 0,
    }
    assert response.json()["run_id"] == RUN_ID
    assert response.json()["is_synthetic"] is True


@pytest.mark.asyncio
async def test_region_summary_counts_fields_without_results_as_cannot_assess(
    seeded_database: Any,
    client: httpx.AsyncClient,
) -> None:
    await seeded_database.fields.insert_one(
        {
            "field_id": "F003",
            "region_id": REGION_ID,
            "geometry": GEOMETRY,
        }
    )

    response = await client.get(f"/api/regions/{REGION_ID}/summary")

    assert response.status_code == 200
    assert response.json()["counts_by_risk"]["cannot_assess"] == 1


@pytest.mark.asyncio
async def test_region_fields_returns_geojson_and_result_properties(
    seeded_database: Any,
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"/api/regions/{REGION_ID}/fields")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 2
    feature = next(item for item in body["features"] if item["properties"]["field_id"] == FIELD_ID)
    assert feature["type"] == "Feature"
    assert feature["properties"]["risk"] == "alert"
    assert feature["properties"]["is_synthetic"] is True
    assert "_id" not in feature["properties"]


@pytest.mark.asyncio
async def test_region_fields_without_result_is_cannot_assess(
    seeded_database: Any,
    client: httpx.AsyncClient,
) -> None:
    await seeded_database.fields.insert_one(
        {
            "field_id": "F003",
            "region_id": REGION_ID,
            "geometry": GEOMETRY,
            "is_synthetic_boundary": True,
        }
    )

    response = await client.get(f"/api/regions/{REGION_ID}/fields")
    field = next(item for item in response.json()["features"] if item["properties"]["field_id"] == "F003")

    assert field["properties"]["risk"] == "cannot_assess"
    assert field["properties"]["confidence"] == 0.0
    assert field["properties"]["is_synthetic"] is True


@pytest.mark.asyncio
async def test_queue_filters_risk_sorts_and_limits(
    seeded_database: Any,
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(
        f"/api/regions/{REGION_ID}/queue?risk=alert&limit=1"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["field_id"] == "F001"
    assert response.json()[0]["risk"] == "alert"

    all_results = await client.get(f"/api/regions/{REGION_ID}/queue")
    assert [row["field_id"] for row in all_results.json()] == ["F002", "F001"]


@pytest.mark.asyncio
async def test_field_detail_returns_latest_result(
    seeded_database: Any,
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"/api/fields/{FIELD_ID}")

    assert response.status_code == 200
    assert response.json()["field_id"] == FIELD_ID
    assert response.json()["risk"] == "alert"
    assert response.json()["is_synthetic"] is True
    assert "password_hash" not in response.text
    assert "_id" not in response.json()


@pytest.mark.asyncio
async def test_timeseries_has_baseline_band_and_date_limited_rainfall(
    seeded_database: Any,
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"/api/fields/{FIELD_ID}/timeseries")

    assert response.status_code == 200
    body = response.json()
    assert body["drop_start"] == "2026-01-14"
    assert [point["date"] for point in body["points"]] == ["2026-01-04", "2026-02-08"]
    assert body["points"][0]["band_low"] == pytest.approx(0.52)
    assert body["points"][0]["band_high"] == pytest.approx(0.64)
    assert body["points"][1]["low_quality"] is True
    assert [point["date"] for point in body["rainfall"]] == ["2026-01-04", "2026-02-08"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "expected_code"),
    [
        ("/api/regions/unknown/summary", "NOT_FOUND"),
        ("/api/regions/unknown/fields", "NOT_FOUND"),
        ("/api/regions/unknown/queue", "NOT_FOUND"),
        ("/api/fields/unknown", "NOT_FOUND"),
        ("/api/fields/unknown/timeseries", "NOT_FOUND"),
    ],
)
async def test_unknown_region_or_field_returns_not_found(
    seeded_database: Any,
    client: httpx.AsyncClient,
    path: str,
    expected_code: str,
) -> None:
    response = await client.get(path)

    assert response.status_code == 404
    assert response.json()["code"] == expected_code
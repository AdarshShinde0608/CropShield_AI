from collections import Counter
from pathlib import Path
import sys
from typing import Any

import httpx
import mongomock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.seed_demo import build_seed_data, load_seed_data


@pytest.mark.asyncio
async def test_seeded_region_fields_endpoint_returns_40_synthetic_features(
    shared_client: httpx.AsyncClient,
    shared_database: Any,
) -> None:
    data = build_seed_data()
    collection_names = (
        "regions",
        "fields",
        "seasons",
        "observations",
        "rainfall",
        "field_results",
        "analysis_runs",
        "validation_reports",
    )
    for name in collection_names:
        await shared_database[name].delete_many({})
        documents = data[name]
        if documents:
            await shared_database[name].insert_many(documents)

    response = await shared_client.get("/api/regions/demo-region/fields")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 40
    assert all(feature["type"] == "Feature" for feature in body["features"])
    assert all(feature["properties"]["is_synthetic"] is True for feature in body["features"])
    risk_counts = Counter(feature["properties"]["risk"] for feature in body["features"])
    assert risk_counts == {
        "normal": 29,
        "watch": 5,
        "alert": 3,
        "cannot_assess": 3,
    }
    assert all("_id" not in feature for feature in body["features"])


def test_seed_loader_is_idempotent_and_preserves_users_and_actions() -> None:
    database = mongomock.MongoClient()["synthetic-seed-test"]
    database.users.insert_one({"email": "existing@example.org"})
    database.actions.insert_one({"action_id": "existing-action"})
    data = build_seed_data()

    load_seed_data(database, data)
    collection_names = (
        "regions",
        "fields",
        "seasons",
        "observations",
        "rainfall",
        "field_results",
        "analysis_runs",
        "validation_reports",
        "users",
        "actions",
    )
    first_counts = {
        name: database[name].count_documents({}) for name in collection_names
    }
    load_seed_data(database, data)
    second_counts = {
        name: database[name].count_documents({}) for name in collection_names
    }

    assert first_counts == second_counts
    assert first_counts["regions"] == 1
    assert first_counts["fields"] == 40
    assert first_counts["observations"] == len(data["observations"])
    current_season_id = next(
        season["season_id"] for season in data["seasons"] if season["role"] == "current"
    )
    assert all(
        row["season_id"] == current_season_id for row in data["observations"]
    )
    assert database.users.count_documents({}) == 1
    assert database.actions.count_documents({}) == 1


def test_seed_loader_refuses_a_database_with_other_regions() -> None:
    database = mongomock.MongoClient()["unsafe-seed-test"]
    database.regions.insert_one({"region_id": "non-demo-region"})

    with pytest.raises(RuntimeError, match="isolated demo database"):
        load_seed_data(database, build_seed_data())

    assert database.regions.count_documents({}) == 1
    assert database.fields.count_documents({}) == 0

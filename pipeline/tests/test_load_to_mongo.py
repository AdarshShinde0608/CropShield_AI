import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from pipeline import load_to_mongo


class _Collection:
    def __init__(self, name: str) -> None:
        self.name = name
        self.indexes: list[tuple[Any, dict[str, Any]]] = []
        self.deletions: list[dict[str, Any]] = []
        self.document: dict[str, Any] | None = None

    def create_index(self, keys: Any, **options: Any) -> None:
        self.indexes.append((keys, options))

    def delete_many(self, query: dict[str, Any]) -> None:
        self.deletions.append(query)

    def delete_one(self, query: dict[str, Any]) -> None:
        self.deletions.append(query)

    def replace_one(
        self, query: dict[str, Any], document: dict[str, Any], **_: Any
    ) -> None:
        self.document = document

    def find_one(self, *_: Any, **__: Any) -> dict[str, Any] | None:
        return self.document

    def update_many(self, *_: Any, **__: Any) -> None:
        return None

    def update_one(self, *_: Any, **__: Any) -> None:
        return None


class _Database:
    def __init__(self) -> None:
        self.collections: dict[str, _Collection] = {}

    def __getattr__(self, name: str) -> _Collection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self.collections.setdefault(name, _Collection(name))


class _Client:
    def __init__(self, database: _Database) -> None:
        self.admin = self
        self.database = database

    def command(self, _: str) -> None:
        return None

    def __getitem__(self, _: str) -> _Database:
        return self.database

    def close(self) -> None:
        return None


def _write_processed_run(directory: Path) -> None:
    (directory / "analysis_run.json").write_text(
        json.dumps(
            {
                "run_id": "run-current",
                "region_id": "region-a",
                "season_id": "2025-26",
                "is_synthetic": True,
                "model_version": None,
                "model_checksum": None,
                "params": {},
            }
        ),
        encoding="utf-8",
    )
    (directory / "fields.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": []},
                        "properties": {"field_id": "field-1"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"field_id": "field-1", "season_id": "2024-25", "date": "2025-01-01"},
            {
                "field_id": "field-1",
                "season_id": "2025-26",
                "date": "2025-11-01",
                "ndvi": 0.4,
                "baseline_median": 0.5,
                "baseline_sigma": 0.1,
                "z": -1.0,
                "pct_dev": -20.0,
            },
        ]
    ).to_csv(directory / "observations.csv", index=False)
    pd.DataFrame(
        [
            {"season_id": "2024-25", "date": "2025-01-01", "rain_mm": 1.0},
            {"season_id": "2025-26", "date": "2025-11-01", "rain_mm": 2.0},
        ]
    ).to_csv(directory / "rainfall.csv", index=False)
    pd.DataFrame(
        [
            {
                "field_id": "field-1",
                "season_id": "2025-26",
                "risk": "watch",
                "evidence": json.dumps(
                    {
                        "latest_observation_date": "2025-11-01",
                        "observed_ndvi": 0.4,
                        "baseline_median": 0.5,
                    }
                ),
                "top_factors": "",
            }
        ]
    ).to_csv(directory / "field_results.csv", index=False)


def test_loader_keeps_current_season_data_and_schema_metadata(
    tmp_path: Path, monkeypatch: Any
) -> None:
    _write_processed_run(tmp_path)
    database = _Database()
    captured: dict[str, list[dict[str, Any]]] = {}
    monkeypatch.setattr(
        load_to_mongo,
        "MongoClient",
        lambda *_args, **_kwargs: _Client(database),
    )
    monkeypatch.setattr(
        load_to_mongo,
        "_upsert_many",
        lambda collection, documents, _keys: captured.__setitem__(
            collection.name, documents
        ),
    )

    summary = load_to_mongo.load_processed_run(tmp_path, "mongodb://unused", "db")

    assert summary["observations"] == 1
    assert summary["rainfall"] == 1
    assert [row["season_id"] for row in captured["observations"]] == ["2025-26"]
    assert [row["season_id"] for row in captured["rainfall"]] == ["2025-26"]
    result = captured["field_results"][0]
    assert result["model_version"] is None
    assert result["model_score"] is None
    assert result["top_factors"] is None
    assert result["decision_threshold"] is None
    assert result["evidence"]["baseline_median"] == 0.5
    assert result["is_synthetic"] is True
    assert database.observations.deletions == [{"field_id": {"$in": ["field-1"]}}]
    assert database.rainfall.deletions == [{"region_id": "region-a"}]

    run = database.analysis_runs.document
    assert run is not None
    assert run["model_version"] is None
    assert run["model_checksum"] is None
    assert database.field_results.indexes[0][0] == [
        ("region_id", 1),
        ("season_id", 1),
        ("run_id", 1),
        ("priority_rank", 1),
    ]
    assert database.rainfall.indexes[0][0] == [
        ("region_id", 1),
        ("season_id", 1),
        ("date", 1),
    ]
    assert database.analysis_runs.indexes[1][0] == [("created_at", -1)]


def test_loader_rejects_non_json_model_fields(tmp_path: Path) -> None:
    path = tmp_path / "field_results.csv"
    pd.DataFrame([{"evidence": "{not-json"}]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="evidence must contain valid JSON"):
        load_to_mongo._records(path)


def test_loader_preserves_model_factors_only_when_serialized_by_model(
    tmp_path: Path,
) -> None:
    path = tmp_path / "field_results.csv"
    factors = [{"feature": "NDVI", "contribution": -0.2}]
    pd.DataFrame([{"top_factors": json.dumps(factors)}]).to_csv(path, index=False)

    assert load_to_mongo._records(path) == [{"top_factors": factors}]

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.core.model import ModelRuntime
from app.services.model_store import ModelStore, process_memory_bytes


class FakeCollection:
    def __init__(self, record: dict[str, Any] | None) -> None:
        self.record = record

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
        return self.record


def _install_model(models_root: Path, version: str) -> dict[str, Any]:
    version_dir = models_root / version
    version_dir.mkdir(parents=True)
    artifact = version_dir / "model.onnx"
    artifact.write_bytes(f"fixture-{version}".encode())
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    card = {
        "version": version,
        "artifact_files": ["model.onnx"],
        "artifact_checksums": {"model.onnx": checksum},
    }
    (version_dir / "model_card.json").write_text(
        json.dumps(card),
        encoding="utf-8",
    )
    return {
        "model_version": version,
        "artifact_checksums": card["artifact_checksums"],
        "status": "active",
        "weights_stored": False,
    }


def _install_runtime_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    def load_verified_onnx(
        model_dir: Path,
        *,
        expected_version: str | None = None,
        expected_checksums: dict[str, str] | None = None,
    ) -> ModelRuntime:
        with (model_dir / "model_card.json").open(encoding="utf-8") as source:
            card = json.load(source)
        if (
            card.get("version") != expected_version
            or card.get("artifact_checksums") != expected_checksums
        ):
            return ModelRuntime(expected_version, None, {}, False, "MODEL_MISMATCH")
        for name, checksum in (expected_checksums or {}).items():
            artifact = model_dir / name
            if hashlib.sha256(artifact.read_bytes()).hexdigest() != checksum:
                return ModelRuntime(expected_version, None, {}, False, "MODEL_MISMATCH")
        return ModelRuntime(
            expected_version,
            card,
            {"model.onnx": "test-runtime"},
            True,
            None,
        )

    monkeypatch.setattr("app.services.model_store.load_model", load_verified_onnx)


def test_store_loads_the_version_named_by_active_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_runtime_loader(monkeypatch)
    record = _install_model(tmp_path, "model-v1")
    store = ModelStore(FakeCollection(record), tmp_path, 3600)

    loaded = asyncio.run(store.refresh_once())

    assert loaded is True
    assert store.ready is True
    assert store.runtime.version == "model-v1"
    assert store.runtime.artifacts["model.onnx"] == "test-runtime"


def test_store_rejects_record_checksum_disagreement_before_loading(
    tmp_path: Path,
) -> None:
    record = _install_model(tmp_path, "model-v1")
    record["artifact_checksums"] = {"model.onnx": "0" * 64}
    store = ModelStore(FakeCollection(record), tmp_path, 3600)

    loaded = asyncio.run(store.refresh_once())

    assert loaded is False
    assert store.ready is False
    assert store.error_code == "MODEL_MISMATCH"


def test_store_rejects_artifact_changed_after_checksum_was_recorded(
    tmp_path: Path,
) -> None:
    record = _install_model(tmp_path, "model-v1")
    (tmp_path / "model-v1" / "model.onnx").write_bytes(b"tampered fixture")
    store = ModelStore(FakeCollection(record), tmp_path, 3600)

    loaded = asyncio.run(store.refresh_once())

    assert loaded is False
    assert store.ready is False
    assert store.error_code == "MODEL_MISMATCH"


def test_failed_refresh_retains_previous_runtime_but_marks_not_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_runtime_loader(monkeypatch)
    record = _install_model(tmp_path, "model-v1")
    collection = FakeCollection(record)
    store = ModelStore(collection, tmp_path, 3600)

    async def refresh_twice() -> tuple[ModelRuntime, bool]:
        assert await store.refresh_once() is True
        previous_runtime = store.runtime
        next_record = _install_model(tmp_path, "model-v2")
        next_record["artifact_checksums"] = {
            "model.onnx": "f" * 64,
        }
        collection.record = next_record
        refreshed = await store.refresh_once()
        return previous_runtime, refreshed

    previous_runtime, refreshed = asyncio.run(refresh_twice())

    assert refreshed is False
    assert store.runtime is previous_runtime
    assert store.runtime.version == "model-v1"
    assert store.ready is False
    assert store.error_code == "MODEL_MISMATCH"


def test_successful_refresh_atomically_replaces_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_runtime_loader(monkeypatch)
    record = _install_model(tmp_path, "model-v1")
    collection = FakeCollection(record)
    store = ModelStore(collection, tmp_path, 3600)

    async def refresh_twice() -> ModelRuntime:
        assert await store.refresh_once() is True
        collection.record = _install_model(tmp_path, "model-v2")
        assert await store.refresh_once() is True
        return store.runtime

    current = asyncio.run(refresh_twice())

    assert current.version == "model-v2"
    assert store.ready is True


def test_process_memory_measurement_returns_positive_resident_bytes() -> None:
    assert process_memory_bytes() > 0

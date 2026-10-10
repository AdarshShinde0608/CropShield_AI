from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.fetch_model import verify_and_install_archive


def _build_archive(path: Path, *, version: str = "test-v1") -> tuple[str, str]:
    artifact = b"opaque model bytes"
    license_text = b"Example license"
    attribution_text = b"Example attribution"
    card = {
        "version": version,
        "artifact_files": ["model.onnx"],
        "artifact_checksums": {
            "model.onnx": hashlib.sha256(artifact).hexdigest(),
            "LICENSE": hashlib.sha256(license_text).hexdigest(),
            "ATTRIBUTION": hashlib.sha256(attribution_text).hexdigest(),
        },
        "license": "Example license",
        "attribution": "Example attribution",
        "license_file": "LICENSE",
        "attribution_file": "ATTRIBUTION",
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("model_card.json", json.dumps(card))
        archive.writestr("model.onnx", artifact)
        archive.writestr("LICENSE", license_text)
        archive.writestr("ATTRIBUTION", attribution_text)
    return hashlib.sha256(path.read_bytes()).hexdigest(), hashlib.sha256(artifact).hexdigest()


def test_verified_archive_installs_model_and_rights_files(tmp_path: Path) -> None:
    archive = tmp_path / "artifact.zip"
    archive_sha256, model_sha256 = _build_archive(archive)

    installed = verify_and_install_archive(
        archive,
        expected_archive_sha256=archive_sha256,
        version="test-v1",
        models_dir=tmp_path / "models",
    )

    assert (installed / "model.onnx").is_file()
    assert (installed / "LICENSE").is_file()
    assert (installed / "ATTRIBUTION").is_file()
    assert hashlib.sha256((installed / "model.onnx").read_bytes()).hexdigest() == model_sha256


def test_archive_checksum_mismatch_does_not_install(tmp_path: Path) -> None:
    archive = tmp_path / "artifact.zip"
    _build_archive(archive)
    models_dir = tmp_path / "models"

    with pytest.raises(ValueError, match="archive SHA-256"):
        verify_and_install_archive(
            archive,
            expected_archive_sha256="0" * 64,
            version="test-v1",
            models_dir=models_dir,
        )

    assert not (models_dir / "test-v1").exists()


def test_model_card_file_checksum_mismatch_does_not_install(tmp_path: Path) -> None:
    archive = tmp_path / "artifact.zip"
    _build_archive(archive)
    invalid_archive = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(invalid_archive, "w") as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "model.onnx":
                data = b"modified model bytes"
            target.writestr(item.filename, data)
    models_dir = tmp_path / "models"

    with pytest.raises(ValueError, match="model file checksum"):
        verify_and_install_archive(
            invalid_archive,
            expected_archive_sha256=hashlib.sha256(invalid_archive.read_bytes()).hexdigest(),
            version="test-v1",
            models_dir=models_dir,
        )

    assert not (models_dir / "test-v1").exists()


def test_archive_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "traversal.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside.txt", "not allowed")

    with pytest.raises(ValueError, match="unsafe path"):
        verify_and_install_archive(
            archive,
            expected_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            version="test-v1",
            models_dir=tmp_path / "models",
        )

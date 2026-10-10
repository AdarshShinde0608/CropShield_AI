from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_UNSAFE_SERIALIZED_SUFFIXES = {".joblib", ".pkl", ".pickle"}


@dataclass(frozen=True)
class ModelRuntime:
    version: str | None
    card: dict[str, Any] | None
    artifacts: dict[str, Any]
    ready: bool
    error_code: str | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(model_dir: Path, relative_path: object) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("artifact paths must be non-empty relative paths")
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("artifact path escapes the model directory")
    path = model_dir / candidate
    resolved_model_dir = model_dir.resolve()
    resolved_path = path.resolve()
    if (
        path.is_symlink()
        or not path.is_file()
        or resolved_model_dir not in resolved_path.parents
    ):
        raise ValueError("artifact must be a regular file inside the model directory")
    return path


def load_model(
    model_dir: Path,
    *,
    expected_version: str | None = None,
    expected_checksums: dict[str, str] | None = None,
) -> ModelRuntime:
    """Verify image artifacts, then fail closed for unsupported model runtimes."""
    card_path = model_dir / "model_card.json"
    if not card_path.is_file():
        code = "MODEL_MISMATCH" if expected_version is not None else "MODEL_NOT_LOADED"
        return ModelRuntime(expected_version, None, {}, False, code)
    try:
        with card_path.open(encoding="utf-8") as source:
            card = json.load(source)
        if not isinstance(card, dict):
            raise ValueError("model card must be an object")
        checksums = card.get("artifact_checksums")
        artifact_names = card.get("artifact_files")
        version = card.get("version")
        if (
            not isinstance(version, str)
            or not version
            or not isinstance(checksums, dict)
            or not checksums
            or not isinstance(artifact_names, list)
            or not artifact_names
        ):
            raise ValueError("model card is missing required artifact metadata")
        if expected_version is not None and version != expected_version:
            return ModelRuntime(version, None, {}, False, "MODEL_MISMATCH")
        if expected_checksums is not None and checksums != expected_checksums:
            return ModelRuntime(version, None, {}, False, "MODEL_MISMATCH")

        verified_paths: dict[str, Path] = {}
        for relative_path, expected in checksums.items():
            path = _artifact_path(model_dir, relative_path)
            if not isinstance(expected, str) or _sha256(path) != expected:
                logger.error(
                    "model_integrity_check_failed",
                    extra={"event": "model_integrity_check_failed"},
                )
                return ModelRuntime(version, None, {}, False, "MODEL_MISMATCH")
            verified_paths[relative_path] = path

        if not all(name in verified_paths for name in artifact_names):
            raise ValueError("every model artifact must have a verified checksum")
        suffixes = {Path(name).suffix.lower() for name in artifact_names}
        if suffixes & _UNSAFE_SERIALIZED_SUFFIXES:
            logger.error(
                "unsafe_model_format_rejected",
                extra={"event": "unsafe_model_format_rejected"},
            )
            return ModelRuntime(version, None, {}, False, "MODEL_FORMAT_UNSUPPORTED")
        if suffixes != {".onnx"}:
            raise ValueError("model artifacts must use the approved ONNX format")

        return ModelRuntime(version, None, {}, False, "MODEL_FORMAT_UNSUPPORTED")
    except (OSError, ValueError, TypeError, json.JSONDecodeError, EOFError):
        logger.error(
            "model_initialization_failed",
            extra={"event": "model_initialization_failed"},
        )
        return ModelRuntime(None, None, {}, False, "MODEL_MISMATCH")
    except Exception as error:
        logger.error(
            "model_initialization_failed",
            extra={
                "event": "model_initialization_failed",
                "error_type": type(error).__name__,
            },
        )
        return ModelRuntime(None, None, {}, False, "MODEL_MISMATCH")

"""Fetch and verify an optional model archive during a native build."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO

_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_CHUNK_SIZE = 1024 * 1024
_UNKNOWN_RIGHTS = {"", "unknown", "none", "n/a", "tbd", "to be determined"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_stream(source: BinaryIO, destination: Path) -> None:
    with destination.open("wb") as output:
        shutil.copyfileobj(source, output, length=_CHUNK_SIZE)


def _safe_member_path(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or ":" in name
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError("artifact archive contains an unsafe path")
    destination = root.joinpath(*relative.parts)
    if root.resolve() not in destination.resolve().parents:
        raise ValueError("artifact archive path escapes its staging directory")
    return destination


def _extract_archive(archive_path: Path, destination: Path) -> None:
    seen: set[str] = set()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            name = info.filename
            if name in seen:
                raise ValueError("artifact archive contains duplicate paths")
            seen.add(name)
            target = _safe_member_path(destination, name.rstrip("/"))
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("artifact archive must not contain symbolic links")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source:
                _copy_stream(source, target)


def _validate_model_directory(model_dir: Path, expected_version: str) -> None:
    card_path = model_dir / "model_card.json"
    with card_path.open(encoding="utf-8") as source:
        card = json.load(source)
    if not isinstance(card, dict) or card.get("version") != expected_version:
        raise ValueError("artifact model card version does not match MODEL_VERSION")
    checksums = card.get("artifact_checksums")
    artifact_files = card.get("artifact_files")
    license_file = card.get("license_file")
    attribution_file = card.get("attribution_file")
    if (
        not isinstance(checksums, dict)
        or not checksums
        or not isinstance(artifact_files, list)
        or not artifact_files
        or any(not isinstance(name, str) or not name for name in artifact_files)
        or not isinstance(card.get("license"), str)
        or card["license"].strip().lower() in _UNKNOWN_RIGHTS
        or not isinstance(card.get("attribution"), str)
        or card["attribution"].strip().lower() in _UNKNOWN_RIGHTS
        or not isinstance(license_file, str)
        or not license_file
        or not isinstance(attribution_file, str)
        or not attribution_file
    ):
        raise ValueError("artifact model card is missing required integrity or rights metadata")
    if not set(artifact_files + [license_file, attribution_file]).issubset(checksums):
        raise ValueError("model card does not checksum model and rights files")

    for relative_name, expected_digest in checksums.items():
        if not isinstance(relative_name, str) or not isinstance(expected_digest, str):
            raise ValueError("model card checksum manifest is malformed")
        path = _safe_member_path(model_dir, relative_name)
        if not path.is_file() or path.is_symlink():
            raise ValueError("model card references a missing regular file")
        if not _SHA256_PATTERN.fullmatch(expected_digest):
            raise ValueError("model card contains an invalid SHA-256 checksum")
        if _sha256_file(path).casefold() != expected_digest.casefold():
            raise ValueError("model file checksum does not match the model card")


def verify_and_install_archive(
    archive_path: Path,
    *,
    expected_archive_sha256: str,
    version: str,
    models_dir: Path,
) -> Path:
    """Verify a build archive and atomically install its model-card directory."""
    if not _VERSION_PATTERN.fullmatch(version):
        raise ValueError("MODEL_VERSION must be a safe version identifier")
    if not _SHA256_PATTERN.fullmatch(expected_archive_sha256):
        raise ValueError("MODEL_ARTIFACT_SHA256 must be a 64-character SHA-256")
    if _sha256_file(archive_path).casefold() != expected_archive_sha256.casefold():
        raise ValueError("model archive SHA-256 does not match MODEL_ARTIFACT_SHA256")

    models_dir.mkdir(parents=True, exist_ok=True)
    target = models_dir / version
    if target.exists() or target.is_symlink():
        raise FileExistsError("target model version already exists")

    with tempfile.TemporaryDirectory(prefix=".model-build-", dir=models_dir) as temporary:
        staging = Path(temporary)
        extracted = staging / "extracted"
        extracted.mkdir()
        _extract_archive(archive_path, extracted)
        _validate_model_directory(extracted, version)
        extracted.replace(target)
    return target


def fetch_model() -> int:
    url = os.environ.get("MODEL_ARTIFACT_URL", "").strip()
    expected_sha256 = os.environ.get("MODEL_ARTIFACT_SHA256", "").strip()
    version = os.environ.get("MODEL_VERSION", "").strip()
    if not url and not expected_sha256 and not version:
        print(
            "No model artifact is configured; the service will remain unready "
            "until a verified supported model is supplied.",
            file=sys.stderr,
        )
        return 0
    if not url or not expected_sha256 or not version:
        raise ValueError(
            "MODEL_ARTIFACT_URL, MODEL_ARTIFACT_SHA256, and MODEL_VERSION must be configured together"
        )
    parsed_url = urllib.parse.urlsplit(url)
    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise ValueError("MODEL_ARTIFACT_URL must use HTTPS")

    models_dir = Path("models")
    with tempfile.TemporaryDirectory(prefix=".model-download-", dir=".") as temporary:
        archive_path = Path(temporary) / "artifact.zip"
        request = urllib.request.Request(url, headers={"User-Agent": "CropShield-build"})

        class HttpsRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(
                self,
                req: urllib.request.Request,
                fp: object,
                code: int,
                msg: str,
                headers: object,
                new_url: str,
            ) -> urllib.request.Request | None:
                if urllib.parse.urlsplit(new_url).scheme != "https":
                    raise ValueError("model artifact redirect must remain on HTTPS")
                return super().redirect_request(req, fp, code, msg, headers, new_url)

        try:
            opener = urllib.request.build_opener(HttpsRedirectHandler)
            with opener.open(request, timeout=120) as response:
                final_url = urllib.parse.urlsplit(response.geturl())
                if final_url.scheme != "https":
                    raise ValueError("model artifact redirect must remain on HTTPS")
                _copy_stream(response, archive_path)
        except (OSError, urllib.error.URLError) as error:
            raise RuntimeError("model artifact download failed") from error

        verify_and_install_archive(
            archive_path,
            expected_archive_sha256=expected_sha256,
            version=version,
            models_dir=models_dir,
        )
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(fetch_model())
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        print(f"Model artifact build step failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

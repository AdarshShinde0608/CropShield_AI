"""Package approved model artifacts and register metadata-only candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pymongo import MongoClient

_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CARD_FIELDS = (
    "name",
    "task",
    "input_specification",
    "output_specification",
    "class_mapping",
    "cutoffs",
    "training_data",
    "limitations",
    "license",
    "attribution",
    "framework_versions",
    "artifact_files",
    "license_file",
    "attribution_file",
)
_UNKNOWN_VALUES = {"", "unknown", "none", "n/a", "tbd", "to be determined"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_source_file(source_dir: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("artifact and attribution file paths must be non-empty strings")
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"file path must stay inside source-dir: {relative}")
    path = source_dir / relative_path
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"required regular file does not exist: {relative}")
    try:
        path.resolve().relative_to(source_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"file path escapes source-dir: {relative}") from exc
    return path


def _validate_evaluation(report_path: Path, version: str) -> dict[str, Any]:
    if not report_path.is_file():
        raise ValueError(f"evaluation report does not exist: {report_path}")
    with report_path.open(encoding="utf-8") as source:
        report = json.load(source)
    primary = report.get("primary", {})
    provenance = primary.get("provenance", {})
    if (
        report.get("evaluation_status") != "complete"
        or report.get("evaluation_type") != "held_out"
        or report.get("generated_by") != "pipeline.evaluate"
        or not provenance.get("dataset")
        or not provenance.get("split")
        or provenance.get("sample_count", 0) <= 0
    ):
        raise ValueError("activation requires a complete held-out report from pipeline.evaluate")
    if provenance.get("synthetic") is not False:
        raise ValueError("synthetic evaluation reports cannot authorize model activation")
    if report.get("model_version") != version:
        raise ValueError("evaluation report model_version does not match requested version")
    return report


def build_export_plan(
    version: str,
    source_dir: Path,
    model_card_path: Path,
    evaluation_path: Path,
    models_dir: Path,
) -> dict[str, Any]:
    """Validate provenance and files without copying or registering anything."""
    if not _VERSION_PATTERN.fullmatch(version):
        raise ValueError("version must contain only letters, digits, dots, underscores, and hyphens")
    source = source_dir.resolve(strict=True)
    models = models_dir.resolve()
    protected = (Path(__file__).resolve().parents[1] / "cropshield-ai").resolve()
    try:
        source.relative_to(protected)
    except ValueError:
        pass
    else:
        raise ValueError("cropshield-ai is protected and cannot be an export source")
    if not source.is_dir():
        raise ValueError("source-dir must be a directory")
    target = models / version
    if target.exists():
        raise FileExistsError(f"model version already exists: {target}")
    with model_card_path.open(encoding="utf-8") as source_file:
        card = json.load(source_file)
    missing = [key for key in _CARD_FIELDS if key not in card]
    if missing:
        raise ValueError(f"model card missing required fields: {', '.join(missing)}")
    if not isinstance(card["artifact_files"], list) or not card["artifact_files"]:
        raise ValueError("model card artifact_files must be a non-empty list")
    if not isinstance(card["framework_versions"], dict) or not card["framework_versions"]:
        raise ValueError("framework_versions must identify the runtime versions")
    for key in ("name", "task", "license", "attribution"):
        value = card[key]
        if not isinstance(value, str) or value.strip().lower() in _UNKNOWN_VALUES:
            raise ValueError(f"model card {key} must be documented and non-empty")
    if not isinstance(card["training_data"], dict) or not card["training_data"]:
        raise ValueError("training_data provenance must be documented")
    if not isinstance(card["limitations"], list) or not card["limitations"]:
        raise ValueError("model card must list known limitations")
    if not isinstance(card["class_mapping"], dict) or not card["class_mapping"]:
        raise ValueError("model card class_mapping must be documented")
    if not isinstance(card["cutoffs"], dict):
        raise ValueError("model card cutoffs must be an object, or an empty object if not applicable")
    inputs = _safe_source_file(source, card["license_file"])
    attribution = _safe_source_file(source, card["attribution_file"])
    artifacts = [_safe_source_file(source, name) for name in card["artifact_files"]]
    if len({path.relative_to(source) for path in artifacts}) != len(artifacts):
        raise ValueError("artifact_files must not contain duplicates")
    if any(path in artifacts for path in (inputs, attribution)):
        raise ValueError("license and attribution files must be separate from model artifacts")
    evaluation = _validate_evaluation(evaluation_path, version)
    card["version"] = version
    card["measured_metrics"] = evaluation
    card["git_commit"] = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    card["artifact_checksums"] = {
        str(path.relative_to(source)): _sha256(path)
        for path in [*artifacts, inputs, attribution]
    }
    return {
        "version": version,
        "source_dir": source,
        "target_dir": target,
        "card": card,
        "evaluation": evaluation,
        "files": [
            (path, Path(str(path.relative_to(source))))
            for path in [*artifacts, inputs, attribution]
        ],
        "checksums_verified": True,
    }


def verify_package_checksums(model_dir: Path) -> bool:
    """Verify the packaged card's SHA-256 manifest against local artifact files."""
    with (model_dir / "model_card.json").open(encoding="utf-8") as source:
        card = json.load(source)
    checksums = card.get("artifact_checksums")
    if not isinstance(checksums, dict) or not checksums:
        return False
    for relative, expected in checksums.items():
        path = _safe_source_file(model_dir.resolve(), relative)
        if not isinstance(expected, str) or _sha256(path) != expected:
            return False
    return True


def write_package(plan: dict[str, Any]) -> Path:
    """Write a new version directory atomically; never overwrite existing versions."""
    target: Path = plan["target_dir"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"model version already exists: {target}")
    staging = Path(tempfile.mkdtemp(prefix=f".{plan['version']}-", dir=target.parent))
    try:
        for source, relative in plan["files"]:
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        (staging / "model_card.json").write_text(
            json.dumps(plan["card"], indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        if not verify_package_checksums(staging):
            raise ValueError("copied artifact checksum verification failed")
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def _metadata_record(card: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "model_version": card["version"],
        "name": card["name"],
        "task": card["task"],
        "input_specification": card["input_specification"],
        "output_specification": card["output_specification"],
        "class_mapping": card["class_mapping"],
        "cutoffs": card["cutoffs"],
        "training_data": card["training_data"],
        "measured_metrics": card["measured_metrics"],
        "limitations": card["limitations"],
        "license": card["license"],
        "attribution": card["attribution"],
        "framework_versions": card["framework_versions"],
        "git_commit": card["git_commit"],
        "artifact_checksums": card["artifact_checksums"],
        "status": status,
        "weights_stored": False,
    }


def _register_candidate(record: dict[str, Any], activate: bool, mongo_uri: str, database_name: str) -> None:
    if activate and record["task"].strip().lower() not in {
        "field-level crop-stress",
        "field-level crop stress",
    }:
        raise ValueError("only a field-level crop-stress model may be activated as the risk model")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        collection = client[database_name].model_artifacts
        collection.create_index("model_version", unique=True)
        if activate:
            with client.start_session() as session:
                with session.start_transaction():
                    collection.replace_one(
                        {"model_version": record["model_version"]},
                        {**record, "status": "candidate"},
                        upsert=True,
                        session=session,
                    )
                    collection.update_many(
                        {"status": "active"},
                        {"$set": {"status": "inactive"}},
                        session=session,
                    )
                    result = collection.update_one(
                        {"model_version": record["model_version"], "status": "candidate"},
                        {"$set": {"status": "active"}},
                        session=session,
                    )
                    if result.matched_count != 1:
                        raise RuntimeError("candidate disappeared during activation")
        else:
            collection.replace_one(
                {"model_version": record["model_version"]},
                {**record, "status": "candidate"},
                upsert=True,
            )
    finally:
        client.close()


def export_model(
    version: str,
    source_dir: Path,
    model_card_path: Path,
    evaluation_path: Path,
    models_dir: Path,
    *,
    activate: bool = False,
    dry_run: bool = False,
    mongo_uri: str | None = None,
    database_name: str | None = None,
) -> dict[str, Any]:
    """Validate, package, and register a candidate model version."""
    plan = build_export_plan(version, source_dir, model_card_path, evaluation_path, models_dir)
    if activate and plan["card"]["task"].strip().lower() not in {
        "field-level crop-stress",
        "field-level crop stress",
    }:
        raise ValueError("only a field-level crop-stress model may be activated as the risk model")
    if dry_run:
        return {
            "status": "dry_run_validated",
            "version": version,
            "target_dir": str(plan["target_dir"]),
            "files": [str(relative) for _, relative in plan["files"]],
            "checksums_verified": plan["checksums_verified"],
            "would_activate": activate,
        }
    effective_uri = mongo_uri or os.getenv("MONGODB_URI")
    effective_database = database_name or os.getenv("MONGODB_DB", "cropshield")
    if not effective_uri:
        raise ValueError("MONGODB_URI is required to register candidate metadata")
    target = write_package(plan)
    if not verify_package_checksums(target):
        raise ValueError(f"packaged checksums failed verification: {target}")
    record = _metadata_record(plan["card"], "candidate")
    _register_candidate(record, activate, effective_uri, effective_database)
    return {
        "status": "active" if activate else "candidate",
        "version": version,
        "target_dir": str(target),
        "checksums_verified": True,
        "weights_stored_in_mongodb": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--model-card", type=Path, required=True)
    parser.add_argument("--evaluation-report", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = export_model(
        args.version,
        args.source_dir,
        args.model_card,
        args.evaluation_report,
        args.models_dir,
        activate=args.activate,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

import json
from pathlib import Path

import pytest

from pipeline.evaluate import evaluate_predictions
from pipeline.export_model import (
    _safe_source_file,
    build_export_plan,
    export_model,
    verify_package_checksums,
    write_package,
)
import pandas as pd


def _write_candidate_files(tmp_path: Path, *, synthetic: bool = False) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir(parents=True)
    (source / "weights.bin").write_bytes(b"reviewed-test-artifact")
    (source / "LICENSE.txt").write_text("Example permitted license", encoding="utf-8")
    (source / "ATTRIBUTION.txt").write_text("Example author attribution", encoding="utf-8")
    card = {
        "name": "Test model",
        "task": "crop-type classification",
        "input_specification": {"fields": ["NDVI"]},
        "output_specification": {"classes": ["crop-a"]},
        "class_mapping": {"crop-a": "Crop A"},
        "cutoffs": {},
        "training_data": {"dataset": "test-only fixture"},
        "limitations": ["Test fixture only"],
        "license": "Example License 1.0",
        "attribution": "Example author",
        "framework_versions": {"python": "3.11"},
        "artifact_files": ["weights.bin"],
        "license_file": "LICENSE.txt",
        "attribution_file": "ATTRIBUTION.txt",
    }
    card_path = tmp_path / "model_card.json"
    card_path.write_text(json.dumps(card), encoding="utf-8")
    predictions = pd.DataFrame(
        [
            {
                "field_id": "field-1",
                "y_true": "crop-a",
                "y_pred": "crop-a",
                "is_synthetic": synthetic,
            }
        ]
    )
    report = evaluate_predictions(
        predictions, "test fixture", "held-out fixture", "test-v1"
    )
    report_path = tmp_path / "evaluation.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return source, card_path, report_path


def test_export_plan_and_package_preserve_artifact_license_and_attribution(tmp_path: Path) -> None:
    source, card, report = _write_candidate_files(tmp_path)
    models = tmp_path / "models"
    plan = build_export_plan("test-v1", source, card, report, models)

    packaged = write_package(plan)

    assert (packaged / "weights.bin").read_bytes() == b"reviewed-test-artifact"
    assert (packaged / "LICENSE.txt").is_file()
    assert (packaged / "ATTRIBUTION.txt").is_file()
    assert verify_package_checksums(packaged)
    (packaged / "weights.bin").write_bytes(b"tampered")
    assert not verify_package_checksums(packaged)


def test_dry_run_has_no_filesystem_or_database_side_effects(tmp_path: Path) -> None:
    source, card, report = _write_candidate_files(tmp_path)
    models = tmp_path / "models"

    result = export_model(
        "test-v1",
        source,
        card,
        report,
        models,
        dry_run=True,
    )

    assert result["status"] == "dry_run_validated"
    assert not models.exists()


def test_export_refuses_synthetic_eval_and_unknown_license(tmp_path: Path) -> None:
    source, card, report = _write_candidate_files(tmp_path, synthetic=True)
    with pytest.raises(ValueError, match="synthetic"):
        build_export_plan("test-v1", source, card, report, tmp_path / "models")

    source, card, report = _write_candidate_files(tmp_path / "unknown")
    details = json.loads(card.read_text(encoding="utf-8"))
    details["license"] = "unknown"
    card.write_text(json.dumps(details), encoding="utf-8")
    with pytest.raises(ValueError, match="license"):
        build_export_plan("test-v1", source, card, report, tmp_path / "models")


def test_export_refuses_protected_model_source_and_path_traversal(tmp_path: Path) -> None:
    protected = Path(__file__).resolve().parents[2] / "cropshield-ai"
    source, card, report = _write_candidate_files(tmp_path)
    with pytest.raises(ValueError, match="protected"):
        build_export_plan("test-v1", protected, card, report, tmp_path / "models")

    with pytest.raises(ValueError, match="stay inside"):
        _safe_source_file(source.resolve(), "../outside.bin")


def test_activation_requires_field_level_stress_task(tmp_path: Path) -> None:
    source, card, report = _write_candidate_files(tmp_path)

    with pytest.raises(ValueError, match="field-level crop-stress"):
        export_model(
            "test-v1",
            source,
            card,
            report,
            tmp_path / "models",
            activate=True,
            dry_run=True,
        )

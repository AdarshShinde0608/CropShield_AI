# CropShield AI model decision record

**Decision date:** 2026-10-10

**Scope:** documentation and rules only. No model code, weights, training, or
runtime behavior is changed by this record.

## Decision

The audited `cropshield-ai` model is **not the crop-stress decision engine**.
Its Random Forest predicts a crop-type class from a single tabular feature row;
its Isolation Forest is a generic per-row outlier detector. Neither is a
validated field-level, baseline-relative crop-stress model for Indian rabi
time-series data.

The existing root pipeline stress detector remains authoritative for
`risk`, `severity`, `confidence`, and `confidence_label` until a replacement
stress model passes the validation gates below. The nested Random Forest may be
evaluated only as optional crop-type context, after its data rights, artifact
provenance, and required feature availability are verified. Its Isolation
Forest and nested hand-written risk rules are not used for project risk.

This is a conditional design, not approval to copy, package, or deploy the
nested files. The user supplied the dataset reference
<https://www.kaggle.com/datasets/abdulahadiltaf/sentinel-2-multispectral-crop-and-landcover-dataset>,
but its license, attribution terms, weight provenance, and permission for
production use or redistribution remain **unknown and unapproved**. The
artifacts have not been deserialized or load-tested. The protected
`cropshield-ai/` tree remains read-only until the user explicitly confirms
migration verification.

## Claims and output policy

- The product may describe the nested classifier's output as a **predicted
  crop-type label** only after its inputs and permitted use are verified.
- It must not describe that classifier, its score, or its Isolation Forest as
  crop-stress, crop-health, or crop-failure detection.
- The classifier's maximum `predict_proba` value is an **uncalibrated model
  score**, not calibrated confidence or probability of crop failure. If shown,
  label it “model score”; otherwise omit it from the UI.
- The model does not produce a validated `normal`, `watch`, `alert`, or
  `cannot_assess` result. Do not map its crop classes, per-row anomaly labels,
  or hand-written `low`/`medium`/`high` output to project risk.
- The root pipeline remains the sole risk mapper:
  - insufficient, stale, or unusable observations/data quality produce
    `cannot_assess`;
  - otherwise the existing pipeline rules determine `normal`,
    `watch`, or `alert`;
  - `severity` is `moderate` or `high` only when that pipeline returns
    `alert`;
  - the existing pipeline `confidence` and `confidence_label` method remains
    the only source of those fields; the classifier's `model_score` never
    feeds them. Neither value is described as a calibrated probability unless
    calibration and validation establish that claim.
- `drop_start` and `evidence` are reported only when supported by pipeline
  observations and the baseline-evidence module. They are not model-derived
  causes.
- Risk labels, alert wording, and advice must continue to say unusual
  vegetation behaviour to inspect/check, never a diagnosis or confirmed cause.

## Pipeline disposition

| Capability | Decision |
|---|---|
| Earth Engine extraction and existing input data | Retain in `pipeline/`; Earth Engine stays out of backend and `ml-service`. |
| Cleaning, date alignment, valid-fraction quality checks, and stale-data gating | Retain. These checks are required to prevent unsupported results and to produce `cannot_assess`. |
| Rainfall context | Retain as contextual evidence only; it does not identify a cause. |
| Baseline-evidence module | Retain as required supporting evidence and for the current fallback risk detector. |
| Existing baseline-based risk rules and their `pipeline/config.py` parameters | Keep as the active risk decision source until a replacement stress model passes validation. This temporarily overrides the proposed removal in the initial P38 outline. |
| Root-pipeline k-means and optional Isolation Forest | Retire from the target inference path as requested. This documentation-only task does not remove or change their current implementation; verify the remaining baseline fallback works before code removal. |
| Nested `cropshield-ai` training scripts and nested risk rules | Do not use as project training/risk logic. Future approved fitting/training belongs only in root `pipeline/train/`. |
| Nested crop-type Random Forest | Optional context experiment only, gated on license/provenance, safe artifact verification, and complete compatible inputs. Until all gates pass, it is disabled. |
| Model weights | Never store in MongoDB. If later approved, include only in a controlled, versioned image/release with a verified checksum. |

All project thresholds and decision constants remain defined in
`pipeline/config.py`; cut-offs must be selected from real validation results,
not inferred from these model artifacts or chosen in this decision record.

## Runtime and serving plan

The audited artifacts are joblib/pickle-style objects and the source manifest
pins scikit-learn 1.5.2 and joblib 1.4.2. The user selected the ONNX/parity
route for the service. The service therefore rejects all `.joblib`, `.pkl`, and
`.pickle` artifacts; those deserialization dependencies are not installed in
the service image. An ONNX runtime adapter, conversion, and prediction-parity
evidence are not yet available, so ONNX candidates also remain unready and
the service cannot currently load a model. Do not reintroduce pickle/joblib
loading. Any later runtime must be validated against trusted source outputs
with a documented parity tolerance before activation.

The seven inspected model artifacts total 337.28 MiB on disk. The largest
single classifier file is about 335 MiB. Peak resident memory, cold-start/load
time, and inference latency have not been measured; disk size does not prove
that the model fits a 512 MB service. G3 therefore remains unpassed.

The system is batch-oriented: no dashboard, map, or chart waits on
request-time model inference. If a future measured service fits the available
memory and startup limits, the controlled pipeline may call its internal HTTP
inference endpoint while producing a run. If it does not fit, use batch-only
inference in a controlled pipeline worker and persist only result metadata and
predictions through the existing pipeline loader. The ML service does not
persist data; its only permitted MongoDB access is a read-only lookup in
`model_artifacts` for `/v1/model-info`. The existing backend serves persisted
results. No service is deployed with unapproved artifacts.

## Gate decisions

| Gate | Evidence and decision |
|---|---|
| **G1 — Task fit** | **Fail for stress detection.** The model tasks are crop-type classification and generic per-row outlier scoring. Decision: optional crop-type context only; current pipeline remains the stress decision engine. |
| **G2 — Weights** | **Pending.** Seven artifacts are present (337.28 MiB), but loadability and integrity have not been tested. The user authorized a future isolated clean-environment loadability test; no such test is part of this documentation-only task. Dataset/model rights remain unresolved, so do not load or package before clearance. |
| **G3 — Footprint** | **Pending measurement.** Resident memory, startup, and latency are unknown. Measure in the target image against the 512 MB planning limit. If it does not fit, choose the user's batch-only fallback; do not claim online suitability. |
| **G4 — Output mapping** | **Fail for risk mapping; pass only for a non-risk context field.** Crop-type labels and an uncalibrated score do not map to the risk vocabulary. No conversion is permitted. Risk and confidence remain pipeline-owned. |
| **G5 — Baseline** | **Fail for replacement.** No comparison on suitable held-out field-season data exists. Retain the baseline-evidence module and existing pipeline risk detector until a replacement passes measured validation. |

No validation metrics or model version are asserted here. Only values produced
by a recorded real run may be documented as measurements.

## Remaining prerequisites

1. Verify and record the Kaggle dataset license, attribution, source provenance,
   and explicit reuse/production/redistribution permissions for both data and
   trained weights.
2. Identify the exact training dataset snapshot and verify that the packaged
   weights were produced from it.
3. Verify the complete required feature row can be produced from approved
   pipeline inputs. The current project observation contract (field/date NDVI,
   `valid_frac`, and rainfall) does not supply the nested model's full bands,
   indices, ratios, or season feature.
4. After items 1–3, perform isolated checksum and loadability tests, followed
   by runtime footprint measurement and, if considering ONNX, prediction
   parity tests.
5. Define real validation data and acceptance criteria before considering any
   model as a stress-risk replacement.
6. Keep `cropshield-ai/` protected until the user confirms migration and the
   required artifacts, attribution, and tests are independently verified in
   the maintained paths.

## P41/P42 readiness record

The user supplied the Kaggle dataset URL, but no dataset files have been placed
in the workspace. Label definitions/provenance and usage rights remain unknown;
sensor product, bands, and resolution were not supplied. The reported India
geography and approximately four-month date span do not establish a labeled,
leakage-safe field/year split. The dataset was not downloaded, and no training,
model evaluation, calibration, robustness run, or model export has occurred.
The model is **not retrained**. No held-out metric is available.

`pipeline/evaluate.py` evaluates an explicit CSV of saved predictions and
labels, records dataset/split/sample/field counts with each metric, and leaves
robustness checks marked not evaluated when corresponding flags are absent.
Synthetic rows are explicitly identified and cannot authorize activation.
`pipeline/export_model.py` packages only explicitly listed artifacts together
with the supplied license and attribution files, verifies SHA-256 checksums,
and writes metadata only to `model_artifacts`. It rejects artifacts sourced
from the protected nested tree. Activation additionally requires a measured,
non-synthetic held-out report, documented usage rights, valid checksums, and a
field-level crop-stress task; the currently audited crop-type model therefore
cannot be activated as the risk model. These tools are implementation only:
their unit-test fixtures are not model evaluation results, and no artifact was
exported or activated.

## Current release verification

The release-workspace inventory found `models/.gitkeep` only and no
`pipeline/model_runtime/` files. The user authorized removal of `cropshield-ai/`
after verifying migration, but the required in-repository weights, model code,
licence, and attribution were not found. The protected tree was therefore left
untouched; migration is not independently verified by this checkout.

The model remains **not retrained**. No model was packaged, loaded, activated,
or deployed. The absent target artifact and unresolved provenance, licence,
task-fit, and safe-runtime gates keep model-backed risk scoring and threshold
preview functionality disabled for release.

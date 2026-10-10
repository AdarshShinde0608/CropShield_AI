# CropShield AI nested-model audit

**Scope:** read-only inspection of `cropshield-ai/` source, manifests, data-file
metadata, and artifact sizes. No code was run from that project, no pickle/joblib
artifact was deserialized, no training was run, and no dependencies were
installed for this audit. `cropshield-ai/` is protected by `AGENTS.md` until the
user explicitly confirms migration verification.

## Summary

The nested project contains two distinct ML tasks: a per-row crop-type
classifier and a per-row Isolation Forest anomaly detector, combined with
hand-written NDVI thresholds and a persistence counter. It is not a trained
field-level crop-stress time-series model. The checked-in code does not establish
that the model data came from India, Sentinel-2, the rabi season, cloud-masked
field medians, or a documented label process. Its default-on-missing-feature
behavior would silently feed zeros for much of this project's input schema.
It is therefore **not ready to replace or augment the current pipeline**.

The inspected nested README, docs files, and license-file search provide no
license or attribution terms: `cropshield-ai/README.md` and the five files in
`cropshield-ai/docs/` are empty in the inspected workspace, and no `LICENSE` or
`COPYING` file was found under `cropshield-ai/`. The code, weights, and data
should not be copied or redistributed until their provenance and licensing are
confirmed.

## Project, model boundary, and application boundary

- The nested project calls itself CropShield AI, but its root
  `cropshield-ai/README.md` is empty. Product purpose and ownership/licensing
  details are consequently not documented there.
- **Model/training material:** `cropshield-ai/ml/preprocess.py`,
  `cropshield-ai/ml/train.py`, `cropshield-ai/ml/train_anomaly.py`,
  `cropshield-ai/ml/inference.py`, the `.pkl` artifacts in
  `cropshield-ai/ml/models/`, CSVs in `cropshield-ai/ml/data/`, and analysis
  notebook `cropshield-ai/ml/notebooks/01_eda.ipynb`. The tracked
  `cropshield-ai/ml/anomaly_model.py` is empty.
- **Separate application, not a model dependency to migrate:** the independent
  FastAPI backend, its authentication, database, routes, and services under
  `cropshield-ai/backend/`; its separate React/Vite application under
  `cropshield-ai/frontend/`; and its Compose/deployment scripts. For example,
  the backend has its own `cropshield-ai/backend/app/main.py`,
  `cropshield-ai/backend/app/config.py`, and
  `cropshield-ai/backend/app/database.py`, while its frontend has its own
  `cropshield-ai/frontend/package.json`.
- `cropshield-ai/backend/app/ml/inference.py` duplicates the ML inference
  implementation and has six same-named, same-sized serialized model files
  under `cropshield-ai/backend/app/ml/models/`. This does not make the backend,
  frontend, auth, database, or deployment configuration part of the model.
  **Do not copy or deploy that separate application** as part of any model
  migration.
- No license or model/dataset attribution instructions could be established
  from the available files. Absence of a license file is not evidence of
  permission to reuse.

## Task, inputs, and outputs

### Crop-type classifier

`cropshield-ai/ml/preprocess.py` creates a `target` from the CSV `Description`
column. It retains the named categories Rice, Wheat, Cotton, Sugarcane, and
Builtup; other descriptions become `Other`, and classes with fewer than ten
rows are dropped. `cropshield-ai/ml/train.py` then drops `Other` before fitting
the classifier. The exact classes actually present in the serialized encoder
were not inspected by deserializing it. The source of the `Description` labels
and the meaning/annotation quality of each label are **unknown**.

The classifier is a Random Forest over one tabular row, not an image or
time-series model. The training code uses 14 engineered columns when all source
columns exist:

- Indices: `NDVI`, `NDWI`, `EVI`, `GNDVI`, `SAVI`.
- Bands: `Red`, `Green`, `Blue`, `NIR`, `SWIR`.
- Derived: `NIR_Red_ratio`, `NDMI`, `Red_NIR_diff`.
- Season indicator: `is_kharif`.

`train.py` configures 300 trees, balanced class weights, `min_samples_split=5`,
and `random_state=42`. No image-patch dimensions, satellite product, band units,
spatial resolution, temporal window length, or region-specific normalization is
specified in these training files. Missing numeric features are filled with
zero in training and at inference; the crop classifier has no fitted feature
scaler. These other details are **unknown**.

Inference returns `crop_type` and `crop_confidence` (the maximum
`predict_proba` value), alongside a separate anomaly score and rule-derived
risk. Crop-type labels describe the training target categories; they do not
represent crop-health states.

### Isolation Forest and hand-written risk rule

`cropshield-ai/ml/train_anomaly.py` removes rows whose `Land` is Builtup, Water,
or Barrenland, then fits a `StandardScaler` and Isolation Forest to up to 11
per-row features: `NDVI`, `NDWI`, `EVI`, `GNDVI`, `SAVI`, `NIR`, `Red`, `SWIR`,
`NIR_Red_ratio`, `NDMI`, and `Red_NIR_diff`. The scaler is fit on all retained
vegetation rows; the code does not restrict this to a normal-only or
baseline-season subset. It sets `contamination=0.08`, 200 trees, and
`random_state=42`.

The detector exposes `decision_function` scores and predictions `-1` (anomaly)
or `1` (inlier), as written in `train_anomaly.py`. In
`cropshield-ai/ml/inference.py`, a hand-written rule combines the anomaly flag,
score, and single-row NDVI into `risk_level` values `low`, `medium`, and `high`:

- NDVI below `0.30` yields `high`.
- NDVI below `0.45` and anomalous yields `high`.
- NDVI below `0.55`, anomalous, and score below `-0.05` yields `medium`.
- Anomaly score below `-0.15` also yields `medium`.
- Otherwise the output is `low`.

These rules are source-code thresholds, not learned risk classes. Their
interpretation is broad vegetation deviation; neither the model nor these rules
identify a cause. `predict_timeseries()` applies the same single-row predictor
to each input and aggregates counts: three or more `high` rows produce overall
`high`; one `high` or at least three `medium` rows produce `medium`; otherwise
it returns `low` (and `unknown` for an empty input). The response includes
per-row predictions, anomaly counts, concern counts, persistence share, an
overall risk string, and explanatory text. It does not accept a documented
field-level season series schema or use dates to check observation spacing.

The callable inference surface is `CropShieldModel.predict()` for one row,
`CropShieldModel.predict_timeseries()` for a list of rows, and `get_model()` for
the cached model instance; `ml/inference.py` also has a script-mode CSV path.
`cropshield-ai/backend/app/ml/inference.py` contains the corresponding
application-side copy and script-mode path.

## Frameworks, artifacts, and footprint

The ML manifest `cropshield-ai/ml/requirements.txt` pins pandas 2.2.3, NumPy
2.1.3, scikit-learn 1.5.2, matplotlib 3.9.2, seaborn 0.13.2, joblib 1.4.2,
Jupyter 1.1.1, and ipykernel 6.29.5. The model code uses pandas, NumPy,
scikit-learn, and joblib. Package-install footprint was not measured.

The inference module loads six `.pkl` files using `joblib.load`; training saves
these and a separate `label_encoder.pkl` using `joblib.dump`. That extra encoder
is present but is not loaded by this inference entry point. They are
joblib/pickle-style serialized Python objects, not Torch, HDF5, ONNX, or
safetensors artifacts. Sizes observed on disk:

| Artifact | Bytes |
|---|---:|
| `ml/models/crop_classifier.pkl` | 351,130,161 |
| `ml/models/isolation_forest.pkl` | 2,533,289 |
| `ml/models/anomaly_scaler.pkl` | 1,295 |
| `ml/models/crop_classifier_label_encoder.pkl` | 585 |
| `ml/models/label_encoder.pkl` | 597 |
| `ml/models/feature_list.pkl` | 135 |
| `ml/models/anomaly_features.pkl` | 108 |
| **All seven pickle artifacts (six inference-loaded plus one extra encoder)** | **353,666,170 bytes (337.28 MiB)** |

Model-analysis images also exist: `ml/models/confusion_matrix.png` (68,682
bytes), `ml/models/feature_importance.png` (51,777 bytes), and
`ml/models/anomaly_analysis.png` (276,646 bytes). Input/intermediate data files
are `ml/data/combined.csv` (32,234,836 bytes),
`ml/data/preprocessed.csv` (39,739,486 bytes), and
`ml/data/anomaly_scored.csv` (13,881,308 bytes), together 85,855,630 bytes.

Artifact files are present, but whether they load successfully and are
compatible with the pinned versions is **unknown**: they were not unpickled.
This is intentional; deserializing pickle/joblib files can execute code. The
Random Forest file alone is about 335 MiB. Peak RAM, actual deserialized size,
startup/load time, and total deployment footprint are **unknown** and were not
benchmarked. The inspected code uses CPU scikit-learn estimators and requests
`n_jobs=-1` for training; it has no GPU framework or explicit GPU requirement.

## Training data and reproducibility

`cropshield-ai/ml/preprocess.py` reads `data/combined.csv` and names its
candidate classes from the `Description` column. The CSV header includes `ID`,
`Season`, `Province`, `District`, `Date`, `Latitude`, `Longitude`, `Code`,
`Land`, `Description`, `Stage`, the listed indices, and spectral band columns.
The dataset's formal name, original source/URL, collection method, region,
calendar years, sensor, resolution, and licensing are **unknown** in the
available code and documentation. `cropshield-ai/docs/data_sources.md` is empty.
There is no evidenced description of how labels were created or reviewed.

For crop classification, `train.py` makes a random, stratified 80/20 split with
`random_state=42`, trains a 300-tree Random Forest, and contains code to compute
and print accuracy and a classification report. No stored run log or numeric
metric result was found, so the actual score is **unknown** and is not claimed
here. A confusion-matrix image is present but is not a substitute for a
documented, reproducible evaluation.

For anomaly detection, `train_anomaly.py` uses the same available dataset rows
and `contamination=0.08`; its `-1`/`1` labels are generated by the Isolation
Forest itself, not a documented externally labeled test set. It prints anomaly
counts and creates descriptive plots, but the actual run output and any
ground-truth precision/recall are **unknown**. No temporal or geographic
holdout split is described for this detector. The scripts contain settings,
but no separate training configuration, environment lock for every transitive
dependency, dataset citation, or verified reproduction instructions.

No training was run as part of this audit.

## Security and operational concerns

- `joblib.load` loads pickle-style artifacts in
  `cropshield-ai/ml/inference.py`; only load files from a verified trusted
  source. Provenance and artifact integrity are not established here.
- The training scripts use working-directory-relative `models/` and `data/`
  paths. The inference constructor derives its model directory from the module
  path, but its CLI reads `data/anomaly_scored.csv` and `data/preprocessed.csv`
  relative to the current working directory.
- `_build_feature_row()` substitutes `0.0` for every absent feature. Missing
  required inputs therefore become valid-looking values rather than a
  validation error. This is particularly unsafe for this project's
  incompatible feature schema.
- The inspected prediction code performs no network calls. It loads local
  model files; its CLI reads local CSVs. No inference-time secret was observed
  in these model files, and secrets were not displayed.
- `n_jobs=-1` requests all available CPU workers during training. Inference
  memory and latency have not been measured. GPU need: none evident from the
  implementation; runtime and peak memory: **unknown**.

## Compatibility with this repository

This repository's intended input is cloud-masked Sentinel-2 median NDVI by
field/date plus `valid_frac`, with CHIRPS rainfall context for an Indian rabi
season. The contract and pipeline description are in
`docs/TECHNICAL_ARCHITECTURE.md` and the corresponding implementation is under
`pipeline/`.

The nested model expects a single tabular row containing several spectral
bands and indices plus a `Season`-derived `is_kharif` feature. This repository's
documented observation inputs do not include all those raw bands, nor the
model's other indices/derived ratios. No direct transform from the field-date
NDVI/valid-fraction/rainfall schema to the nested model's feature schema is
documented. `valid_frac`, CHIRPS rainfall, baseline-relative values, and
observation quality are not used by this predictor.

The model has no explicit DOS window or field-season temporal feature
engineering. Its “time series” method counts per-row outputs without using
date gaps or seasonal alignment. Its output `low/medium/high` cannot be mapped
to this project's `normal/watch/alert/cannot_assess` vocabulary without a
separate, validated policy. It also emits crop-type guesses, which this
project's current API does not promise.

**Compatibility assessment:** not drop-in compatible. Do not route current
pipeline records into it by filling missing columns with zero, and do not
translate its risk labels into current API risks without data provenance,
domain validation, and an explicitly approved mapping. The existing
statistical baseline remains the applicable model until migration gates are
resolved.

## Gates G1–G5

The gates below use the order named in the request: task fit, weights, footprint,
output mapping, and baseline.

| Gate | Evaluation | Status |
|---|---|---|
| **G1 — Task fit** | Crop-type classification plus per-row generic outlier detection is not the same as field-level, baseline-relative crop-stress detection over an Indian rabi time series. Dataset domain is unknown. | **FAIL / unverified** |
| **G2 — Weights** | Required `.pkl` artifacts are present, but were not deserialized or tested for loadability, integrity, or version compatibility. | **PARTIAL; loadability unknown** |
| **G3 — Footprint** | Seven pickle artifacts total 337.28 MiB; crop classifier alone is about 335 MiB. Peak RAM, load time, dependency-install size, and inference latency are unknown. | **FAIL pending an approved measured budget** |
| **G4 — Output mapping** | Crop labels and `low/medium/high` plus `-1/1` anomaly output do not match the API risk vocabulary; no validated mapping exists. | **FAIL** |
| **G5 — Baseline** | No comparison against this repository's robust baseline/persistence pipeline or its held-out Indian field-season data is documented. Numeric external validation evidence is unavailable. | **FAIL / evidence absent** |

## Open questions for the user

1. What is the original dataset's name, source URL, license, attribution notice,
   region, year range, sensor/product, and resolution?
2. Who created the `Description` labels, what evidence defines each class, and
   are these particular weight/data files approved for redistribution and
   production use?
3. Is the desired migration target crop-type classification, anomaly
   cross-checking, or crop-stress risk classification? Which output, if any,
   should the product expose?
4. What are the allowed serialized-weight, memory, startup-time, and
   dependency-footprint budgets for deployment?
5. What field-season ground truth and acceptance metric/split should be used to
   compare a candidate against the existing robust-z/persistence baseline?
6. Should the nested application remain entirely excluded from migration, as
   this audit assumes, or is there a separately approved component list?
7. What exact event will count as “migration verified” and explicitly release
   the `cropshield-ai/` protection in `AGENTS.md`?

# CropShield AI
## Software Requirements Specification

**Status:** Draft  
**Style:** IEEE 830  
**Product:** CropShield AI (SPACE-05)

> **Source note:** This SRS follows `AGENTS.md`, the SPACE-05 problem statement, and the architecture decisions, interfaces, and data model documented in `docs/TECHNICAL_ARCHITECTURE.md`. Values shown as examples are illustrative, not measured results.

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) defines the functional and non-functional requirements for CropShield AI, an early-warning system that uses public multispectral satellite observations to identify unusual field-level vegetation behaviour. It is intended for implementers, testers, project stakeholders, and operators.

### 1.2 Scope

The initial product covers one selected agricultural region and one current growing season. It obtains public satellite observations, derives vegetation-index time series, compares the current season with a historical baseline, and presents field-level results in a map and inspection queue. The initial implementation profile uses Sentinel-2, NDVI, the rabi season window (1 November through 31 March), and precomputed pipeline results stored in MongoDB. CHIRPS rainfall may be used for regional context.

The offline Python pipeline performs extraction, processing, scoring, validation, and database loading. A FastAPI service provides authenticated application APIs. A React web client presents the map, field details, queue, action tracking, and methodology. The web service does not call Earth Engine or recompute scores.

The product communicates unusual vegetation behaviour for inspection. It does not assert a confirmed cause, crop failure, or a probability of yield loss.

### 1.3 Definitions, acronyms, and abbreviations

| Term | Definition |
|---|---|
| CHIRPS | Climate Hazards Group InfraRed Precipitation with Station data, a gridded precipitation dataset used to provide rainfall context. |
| DOS | Day of season. In this project, the season-day count starts on 1 November. |
| DOS window | A configured grouping/window of season days used when regularising observations and constructing comparisons. |
| MAD | Median absolute deviation: the median of the absolute differences between observations and their median; a robust measure of spread. |
| NDVI | Normalized Difference Vegetation Index, `(NIR - Red) / (NIR + Red)`, calculated from near-infrared and red reflectance. |
| VCI | Vegetation Condition Index, commonly calculated as `(NDVI - NDVI_min) / (NDVI_max - NDVI_min) × 100` for a defined historical period. It is not a diagnosis and is not required by the initial NDVI-only scope. |
| Earth Engine (EE) | Google Earth Engine, used by the offline pipeline to access public geospatial datasets. |
| Field | A mapped agricultural parcel represented by a GeoJSON Polygon and identified by a field ID. |
| Baseline | Historical, season-aligned observations used to estimate expected NDVI behaviour for a field and DOS window. |
| Analysis run | A pipeline execution identified by a unique run ID, with its creation time, parameters, synthetic-data flag, field count, and notes. |
| Synthetic data | Demo or test data that is not an observed real-world result and is explicitly marked `is_synthetic=true`. |

### 1.4 References

- `AGENTS.md` — project rules, component boundaries, vocabularies, and implementation constraints.
- `docs/TECHNICAL_ARCHITECTURE.md` — canonical architecture, interfaces, collections, and constants.
- `01_architecture_and_file_structure.md` — available architecture reference used for this draft.
- SPACE-05 problem statement supplied with this request.

### 1.5 Overview

Section 2 describes the product context and constraints. Section 3 defines functional requirements. Sections 4–7 specify quality attributes, external interfaces, data, and exclusions. Section 8 maps the problem goals to functional requirements.

## 2. Overall description

### 2.1 Product perspective

CropShield AI is a monorepo containing three separately deployable parts:

- **Pipeline:** offline Python processing; the only component that accesses Earth Engine.
- **Backend:** asynchronous FastAPI application providing auth, read APIs, methodology, and user action storage.
- **Frontend:** React web application for the map, field details, inspection queue, action tracking, and multilingual interface.

MongoDB is the persistence layer between the offline pipeline and online backend. The pipeline writes precomputed results; the backend reads them and writes user actions. The frontend accesses data only through the backend API.

### 2.2 Product functions

At a high level, the product shall:

1. Extract public satellite observations for the selected region and season.
2. Clean and regularise observations, compute a historical NDVI baseline, and score current-season deviations.
3. Add persistence, onset, rainfall context, confidence, and inspection priority to field results.
4. Persist observations, results, run parameters, and validation reports in MongoDB.
5. Authenticate users and serve results through a REST API.
6. Display field risk and supporting evidence in a map, detail view, and ranked queue.
7. Let users record and update field inspection actions.
8. Explain the methodology, thresholds, validation metrics, and limitations.

### 2.3 User classes and characteristics

| User class | Expected use |
|---|---|
| Officer | Reviews region-wide risk, prioritises inspections, opens field evidence, and records action outcomes. |
| Farmer | Reviews field-level information and action status where access is provided. |
| Pipeline operator/developer | Configures and runs the offline extraction and analysis process, reviews validation output, and loads results. |

Users of the web client are expected to have a modern browser and an internet connection to the deployed application. The pipeline operator requires configured access to the selected public data services and MongoDB.

### 2.4 Operating environment

- Backend: Python 3.11 or later, FastAPI, Pydantic v2, Motor, PyJWT, and bcrypt.
- Pipeline: Python with pandas, NumPy, and scikit-learn; Earth Engine access is isolated to `pipeline/ee_extract.py`.
- Frontend: React, Vite, strict TypeScript, Tailwind, React Router, TanStack Query, Axios, react-leaflet, Recharts, and i18next.
- Database: MongoDB; MongoDB 7 is the local Compose profile.
- Earth Engine credentials: service-account identity and key supplied through environment/configuration, never committed to source control.

### 2.5 Design and implementation constraints

1. `docs/TECHNICAL_ARCHITECTURE.md` is the source of truth for structure, API contract, collections, constants, and risk vocabulary.
2. Backend code shall not import from `pipeline/` and shall not call Earth Engine. Frontend code shall not contain secrets.
3. Earth Engine access shall use a service account. Credentials, `.env` files, and `secrets/` contents shall not be committed.
4. Thresholds and constants shall be defined only in `pipeline/config.py`; each analysis run shall persist the parameters used.
5. Risk values shall be `normal`, `watch`, `alert`, or `cannot_assess`. `severity` shall be `moderate` or `high` only for `alert`. `confidence_label` shall be `high`, `medium`, or `low`.
6. Missing/NaN observations shall not be silently interpreted as zero.
7. Advice shall use inspection-oriented language (“inspect” or “check”) and shall not claim “pest attack” or “drought confirmed”.
8. Synthetic data shall carry `is_synthetic=true`, and the UI shall visibly identify it.
9. The initial analysis is a batch/offline workflow; the backend serves stored results rather than calculating risk on demand.

### 2.6 Assumptions and dependencies

- A valid field-boundary dataset and region definition are available for the selected region.
- Required public satellite observations are accessible through the configured Earth Engine project and service account.
- Historical observations are available for the selected baseline seasons. A field without enough valid baseline data may be reported as `cannot_assess`; it shall not be assigned a fabricated baseline.
- MongoDB is reachable by both the pipeline loader and backend.
- A successful pipeline run has completed before non-synthetic map and detail data are expected.
- The initial profile follows the available architecture reference’s rabi window and season-aligned baseline. The chosen current season and baseline seasons shall be explicit in the run metadata.
- CHIRPS availability is a dependency only for rainfall-context output; lack of rainfall data shall not invalidate otherwise usable NDVI observations.

## 3. Specific requirements

Priority meanings: **Must** is required for the initial usable product; **Should** is important but can be deferred without invalidating the core flow; **Could** is desirable if the implementation and data support it.

### 3.1 Functional requirements

#### Data extraction

- **FR-01 — Must:** The offline pipeline shall accept a configured region boundary, selected season, satellite collection, and date range, and extract the configured spectral observations and acquisition metadata through Earth Engine.
- **FR-02 — Must:** The initial configured profile shall use Sentinel-2 observations for NDVI analysis. A run shall identify the source collection and region/season used so results can be interpreted and reproduced.
- **FR-03 — Should:** When rainfall context is enabled, the pipeline shall obtain CHIRPS precipitation observations for the configured region and analysis dates and retain the dates and values used. Failure or absence of rainfall context shall be distinguishable from a measured zero-rain value.

#### Cleaning and baseline

- **FR-04 — Must:** The pipeline shall apply the configured quality/cloud filtering, valid-observation checks, and cleaning rules before generating NDVI observations. It shall record validity/quality indicators and shall not convert missing or NaN values to zero.
- **FR-05 — Must:** The pipeline shall derive NDVI from the selected red and near-infrared reflectance, associate observations with DOS starting on 1 November, and regularise observations using the configured season-day window and interpolation-gap rules.
- **FR-06 — Must:** For each field and comparable DOS window, the pipeline shall calculate the historical baseline median and robust spread using the configured baseline seasons and minimum-data rules. It shall retain the baseline sample count/years and mark fields that lack sufficient data as not assessable.

#### Anomaly scoring, persistence, onset, and context

- **FR-07 — Must:** The pipeline shall calculate configured anomaly measures for each eligible current-season observation, including robust z-score and percentage deviation from the baseline, and assign a risk value from the defined risk vocabulary using thresholds in `pipeline/config.py`.
- **FR-08 — Must:** The pipeline shall evaluate configured persistence rules across observations and shall identify the onset (`drop_start`) of a qualifying unusual trend when onset can be established. Results shall distinguish insufficient/stale evidence from normal observations.
- **FR-09 — Should:** Where rainfall data are available, the pipeline shall attach a labelled rainfall context to each relevant result without presenting the context as a confirmed cause of an NDVI anomaly.
- **FR-10 — Must:** The pipeline shall calculate a confidence value in the range 0 to 1 and a `confidence_label` in `high`, `medium`, or `low`, using documented configured evidence-quality rules. Missing evidence shall lower or invalidate confidence as defined by those rules, not be imputed as healthy vegetation.
- **FR-11 — Must:** The pipeline shall rank eligible field results for inspection and persist both `priority_score` and `priority_rank`. Ranking inputs and configured constants shall be traceable to the analysis run.

#### Storage and analysis runs

- **FR-12 — Must:** The pipeline shall write field, season, observation, rainfall (when available), field-result, analysis-run, and validation-report data to their designated MongoDB collections using stable IDs and the documented field names.
- **FR-13 — Must:** Each run shall store its unique `run_id`, creation time, parameters/constants used, synthetic-data flag, number of fields, and notes. Every result presented as synthetic shall carry `is_synthetic=true`.

#### Map and field detail

- **FR-14 — Must:** The web client shall display a region map of field boundaries with each field’s current risk, severity when applicable, confidence label, and synthetic-data status. Risk shall be expressed with an icon and text label as well as any colour treatment.
- **FR-15 — Must:** The web client shall provide a field detail view with current result, available NDVI time series and baseline evidence, observation quality/interpolation indicators, onset date when known, available rainfall context, confidence, advice, and inspection actions.
- **FR-16 — Must:** The map and field detail views shall show explicit loading, empty, and error states. A synthetic result shall trigger a visible synthetic-data banner.

#### Inspection queue

- **FR-17 — Must:** The web client shall provide a region inspection queue ordered by the backend’s `priority_rank`, show the risk and confidence labels, and allow filtering by risk and requesting a bounded result count as supported by the API.
- **FR-18 — Must:** Selecting a queue item shall open the corresponding field detail view without losing the field identity.

#### Authentication

- **FR-19 — Must:** The backend shall allow a user to register with a valid email and a password of at least eight characters, store only a bcrypt password hash, and return a bearer access token on successful registration or login.
- **FR-20 — Must:** The backend shall validate HS256 bearer tokens with a 60-minute expiry and reject invalid or expired tokens with HTTP 401. Passwords and secret values shall not be logged.
- **FR-21 — Must:** Endpoints shall require authentication except for health, registration, login, and methodology endpoints. The backend shall return errors in `{"detail": string, "code": string}` form.
- **FR-22 — Must:** The backend shall obtain allowed CORS origins from `CORS_ORIGINS`; wildcard origins shall not be used in production.

#### Actions tracking

- **FR-23 — Must:** An authenticated user shall be able to create an action for a field with a status from `pending`, `done`, or `needs_expert`, an optional note, and creation/update timestamps.
- **FR-24 — Must:** An authenticated user shall be able to retrieve their actions for a field and update an action’s status or note. The API shall associate each action with its user and field.

#### Language switch and methodology

- **FR-25 — Must:** The frontend shall provide English (`en`), Marathi (`mr`), and Hindi (`hi`) language selection, and shall use translation keys rather than hardcoded user-facing UI strings.
- **FR-26 — Must:** The frontend shall render Devanagari text using a suitable Noto Sans Devanagari fallback font.
- **FR-27 — Must:** The Methodology page shall describe data sources, processing steps, configured thresholds, risk/confidence interpretation, validation metrics when available, and limitations. Validation metrics shall be sourced only from `pipeline/validate.py` output; unavailable metrics shall be labelled unavailable rather than estimated.

## 4. Non-functional requirements

#### Performance

- **NFR-01 — Must:** On the seeded-data acceptance configuration, the map shall become usable in under 3 seconds. Measure from navigation to the map view until the field layer and its risk labels are rendered, with the seeded MongoDB/API available; record the test environment and result. This target is a requirement, not a claim of achieved performance.
- **NFR-02 — Should:** The backend shall use indexed MongoDB queries for region, field, season, priority-rank, and action lookups as defined by the data model. Performance verification shall use representative seeded records and report the observed environment and measurements; no unmeasured latency target is implied.

#### Security

- **NFR-03 — Must:** Secrets, Earth Engine service-account keys, JWT secrets, and `.env` files shall be provided through environment/configuration or a secret manager and shall not be stored in the frontend or committed to version control.
- **NFR-04 — Must:** Passwords shall be bcrypt-hashed and excluded from API responses. Database projections and response schemas shall prevent `password_hash` from leaving the database layer.
- **NFR-05 — Must:** The backend shall validate inputs with Pydantic and enforce the documented authentication requirements. CORS shall use configured origins and disable credentialed cross-origin access for bearer-token requests.
- **NFR-06 — Must:** Production deployment shall use HTTPS and security headers supplied/configured by the hosting platform.

#### Accessibility and internationalisation

- **NFR-07 — Must:** Risk shall never be conveyed by colour alone; each risk state shall have a visible text label and icon.
- **NFR-08 — Must:** Primary navigation, language selection, map field selection, queue actions, and form actions shall be operable by keyboard and have programmatic accessible names. Text shall remain legible when browser text scaling is increased.
- **NFR-09 — Must:** All user-facing interface text shall be available through i18n resources for English, Marathi, and Hindi. Missing translation keys shall be detectable during development/test and shall not silently replace translated application content with raw keys in production.
- **NFR-10 — Must:** Marathi and Hindi interface content shall render Devanagari characters without missing-glyph boxes.

#### Reliability and usability

- **NFR-11 — Must:** The backend shall distinguish no data, unavailable data, and measured zero values. An unavailable/failed dependency shall not be represented as a successful empty or zero-valued observation.
- **NFR-12 — Must:** Every data view shall communicate loading, empty, and error conditions, and provide a usable retry/navigation path where retry is meaningful.
- **NFR-13 — Must:** If a current field result cannot be assessed due to missing or stale evidence, the system shall present `cannot_assess` rather than `normal`.
- **NFR-14 — Must:** Synthetic data and results shall remain identifiable as synthetic throughout pipeline storage, API responses, and the frontend.

#### Reproducibility and maintainability

- **NFR-15 — Must:** The pipeline shall be composed of testable processing functions, and each major cleaning, baseline, scoring, and confidence stage shall have automated unit tests using synthetic fixtures.
- **NFR-16 — Must:** An analysis run shall persist all configured analysis constants used to produce it. The Methodology page and stored results shall identify the associated run.
- **NFR-17 — Should:** Given the same versioned input data and configuration, a pipeline run shall be repeatable; run metadata shall include enough information to identify the data source, season, parameters, and output. Exact bit-for-bit equality is not promised unless the implementation establishes and tests it.
- **NFR-18 — Must:** Each backend route shall have at least one automated test. API and pipeline errors shall be surfaced using the documented error format or explicit pipeline failure output, not silently converted into successful results.

## 5. External interface requirements

### 5.1 User interfaces

The web application shall provide login and registration, dashboard/map, field detail, inspection queue, action tracking, methodology, not-found, and language-switching views. The interface shall use risk icons and labels, show synthetic-data banners, and provide loading/empty/error states for data views.

### 5.2 Software interfaces — REST API

The backend API base path is `/api`. JSON is used for request and response bodies. Errors use `{"detail": "message", "code": "SOME_CODE"}` with an appropriate HTTP status. Bearer authentication is required except where noted below.

| Method | Path | Authentication | Purpose |
|---|---|---|---|
| GET | `/health` | No | Service health. |
| POST | `/auth/register` | No | Register and return access token and user. |
| POST | `/auth/login` | No | Authenticate and return access token and user. |
| GET, PATCH | `/auth/me` | Yes | Read current user; update name or language. |
| GET | `/regions` | Yes | List regions and latest-run information. |
| GET | `/regions/{region_id}/summary` | Yes | Risk counts, latest observation date, run ID, synthetic flag. |
| GET | `/regions/{region_id}/fields` | Yes | GeoJSON FeatureCollection of region fields and result properties. |
| GET | `/regions/{region_id}/queue` | Yes | Ranked inspection queue; supports risk and limit query parameters. |
| GET | `/fields/{field_id}` | Yes | Full field result. |
| GET | `/fields/{field_id}/timeseries` | Yes | Observations, baseline evidence, rainfall when available, and onset. |
| GET, POST | `/fields/{field_id}/actions` | Yes | Read current user’s field actions; create an action. |
| PATCH | `/actions/{action_id}` | Yes | Update action status or note. |
| GET | `/methodology` | No | Methods, thresholds, validation metrics when available, and limitations. |

The endpoint paths and response shapes above follow `docs/TECHNICAL_ARCHITECTURE.md`.

### 5.3 Software interfaces — Earth Engine

Only `pipeline/ee_extract.py` shall access Earth Engine. The pipeline shall authenticate using a service account configured by environment variables and a protected JSON key file. It shall request the configured public satellite collection and region/date subset and preserve source/date metadata needed to trace observations. The backend and frontend shall not receive Earth Engine credentials.

### 5.4 Software interfaces — MongoDB

The backend shall use Motor for asynchronous access. The pipeline loader writes computed data; the backend shall not recompute scores. The expected collections are:

`users`, `regions`, `fields`, `seasons`, `observations`, `rainfall`, `field_results`, `analysis_runs`, `validation_reports`, and `actions`.

Collection fields, uniqueness, and query indexes shall follow the available architecture reference and be reconciled with the canonical technical architecture. The database shall not be used to store raw satellite pixel imagery.

## 6. Data requirements

### 6.1 Persistent data

| Entity/collection | Required data and purpose |
|---|---|
| `users` | Email, bcrypt `password_hash`, name, role (`officer`/`farmer`), language, creation time. Email is unique. |
| `regions` | Region name, state, bounding box, centroid. |
| `fields` | Region and field IDs, name, GeoJSON Polygon geometry, area in hectares, synthetic-boundary flag, and optional cluster. Field IDs are unique; geometry supports 2dsphere queries. |
| `seasons` | Season ID, label, start/end dates, and role (`baseline`/`current`). Season ID is unique. |
| `observations` | Field/season IDs, date, DOS, NDVI, valid fraction, baseline median/spread, z-score, percentage deviation, interpolation flag, and quality flag. `(field_id, season_id, date)` is unique. |
| `rainfall` | Region ID, date, rainfall amount, rolling 14/30-day totals and rainfall anomaly when available. Region/date is indexed. |
| `field_results` | Field/region/season/run IDs; risk, severity, confidence and label; score/deviation, onset/latest observation, valid-observation count, baseline years, rainfall context, advice key/text, priority score/rank, and optional model flag. |
| `analysis_runs` | Unique run ID, creation timestamp, all used parameters, synthetic flag, field count, and notes. |
| `validation_reports` | Run ID and only measured validation outputs, including leave-one-year-out and injection/threshold-sweep results when produced. |
| `actions` | User/field IDs, status (`pending`/`done`/`needs_expert`), note, creation/update timestamps. Actions are queryable by field and user. |

### 6.2 Data quality and retention rules

1. Missing, invalid, or NaN satellite values shall remain distinguishable from zero-valued measurements.
2. Quality filtering and interpolation shall be governed by `pipeline/config.py`; interpolated and low-quality observations shall be flagged.
3. Baseline statistics shall retain the number/identity of usable baseline seasons needed to assess their sufficiency.
4. Risk, confidence, severity, synthetic status, and analysis-run identity shall be persisted and returned without renaming their documented fields.
5. Synthetic records shall be explicitly marked. Synthetic results shall never be presented as measured regional observations.
6. This SRS does not set a retention or deletion period. The project owner must define one before production deployment.

## 7. Limitations and out-of-scope items

- The product does not predict yield, crop failure, or probability of crop loss.
- NDVI anomalies do not identify their cause. The system shall not diagnose drought, pests, disease, nutrient deficiency, or late sowing.
- Risk results are inspection signals (“unusual vegetation behaviour, inspect”), not confirmed damage.
- The initial product does not introduce a new vegetation index, a deep-learning model, or a supervised diagnosis model. Optional statistical methods shall remain subordinate to the documented configured scoring method.
- The initial scope is one selected region and one current growing season, with a historical baseline; it is not a national monitoring service or a general multi-region operations platform.
- Satellite cloud, missing observations, field-boundary quality, mixed land cover, and limited baseline seasons can reduce confidence or make a field not assessable.
- Rainfall context is contextual evidence only and cannot establish the cause of vegetation behaviour.
- No guaranteed availability, update cadence, or end-to-end extraction runtime is specified in this SRS.
- Landsat processing is not part of the initial Sentinel-2 profile. Supporting Landsat or mixing sensor histories requires an explicit architecture/configuration decision and validation of sensor comparability before inclusion.

## 8. Traceability

| SPACE-05 problem goal | Corresponding requirements | Verification evidence |
|---|---|---|
| Use public multispectral satellite imagery for a chosen agricultural region. | FR-01, FR-02, FR-03; NFR-03; interface requirements 5.3 | Run extraction against the configured region/date range; inspect run source metadata; verify credentials are external to version control and web components. |
| Compute vegetation health indices over time. | FR-04, FR-05, FR-06, FR-15; data requirements 6.1–6.2 | Unit tests for cleaning, NDVI/DOS calculation, baseline, and time-series response; verify missing observations are not represented as zero. |
| Detect anomalous stress trends against the historical baseline. | FR-06 through FR-11, FR-13, FR-27 | Pipeline tests cover baseline sufficiency, anomaly thresholds, persistence/onset, context, confidence, ranking, and run parameter provenance. |
| Generate a simple field-level early-warning map. | FR-14, FR-16, FR-17, FR-18; NFR-01, NFR-07, NFR-12, NFR-14 | Seeded-data acceptance test verifies field-level labels and visible synthetic state; measure map usability time against the under-3-second target. |
| Limit scope to one region, one growing season, and a standard index such as NDVI. | Scope 1.2; FR-01, FR-02, FR-05, FR-06; limitations in Section 7 | Configuration and run metadata identify exactly one selected region/current season, the baseline seasons, date window, and NDVI source/index for the initial analysis. |
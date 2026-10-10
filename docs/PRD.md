# CropShield AI — Product Requirements Document

**Status:** Draft for MVP planning  
**Audience:** Product, engineering, pilot partners  
**Related documents:** `AGENTS.md`, `SRS.md`, `TECHNICAL_ARCHITECTURE.md`

## 1. Product vision

Help agricultural extension teams use public satellite observations to decide which fields may merit a closer look, while making the evidence and uncertainty understandable to officers and farmers in local languages.

CropShield AI is an inspection-prioritisation aid. An alert means “unusual vegetation behaviour, inspect”; it is not a crop-failure prediction or a diagnosis.

## 2. Problem and why now

Extension officers have limited time for field visits, while a region may contain many fields and repeated observations. A map of raw vegetation-index values alone does not show whether a field differs from its own historical seasonal pattern, whether the signal persists, or how much evidence supports it.

Public multispectral imagery and open precipitation data make it possible to build a low-cost, repeatable screening workflow. A field-level baseline, transparent anomaly evidence, confidence, and an inspection queue can make that data more actionable. Cloud gaps, boundary quality, and limited ground truth still constrain interpretation; the product must communicate those limits clearly.

## 3. Users and personas

### Primary persona — Agricultural extension officer

- Works across a defined agricultural region and has limited inspection capacity.
- Needs to identify which fields merit a visit, understand the evidence quickly, and record whether an inspection is pending, complete, or needs expert follow-up.
- Needs freshness, confidence, and synthetic-data status to be explicit before acting.
- Success is better-informed prioritisation, not a claim that every alert is correct.

### Secondary persona — Smallholder farmer

- Uses a phone and may prefer Marathi or Hindi over English.
- Needs a simple explanation of what an unusual vegetation signal means and does not mean.
- Benefits from read-aloud explanation when reading is inconvenient; the MVP does not require voice input.
- Must not be told that a crop is damaged or that drought/pest cause is confirmed.

### Supporting user — Pipeline operator/developer

- Configures the region, seasons, satellite source, and analysis parameters.
- Runs and validates the offline pipeline, loads data, and confirms whether the dataset is synthetic or observed.

## 4. MVP user stories and acceptance criteria

### Officer: prioritise and inspect

**Story:** As an extension officer, I want to see a ranked field map and queue so I can direct limited inspection time toward fields with unusual, sufficiently supported vegetation behaviour.

**Acceptance criteria**

1. After valid login, the dashboard displays fields for the configured region with risk text and icon; colour is not the sole signal.
2. Results identify the latest observation date, confidence label, and synthetic status.
3. The queue orders fields by the pipeline-provided `priority_rank` and can filter by risk using the documented API.
4. A field with insufficient/stale evidence is shown as `cannot_assess`, not `normal`.
5. Map and queue expose loading, empty, and error states.
6. On seeded data, the map becomes usable in under 3 seconds, measured from navigation through field-layer and risk-label rendering; the environment and result are recorded.

### Officer: understand a field

**Story:** As an extension officer, I want to open a field and review its time series, baseline, quality flags, and rainfall context so I can interpret the signal before visiting.

**Acceptance criteria**

1. Selecting a field opens its current result and its observation time series.
2. The detail view distinguishes measured, interpolated, low-quality, stale, and unavailable data where those states apply.
3. It shows baseline evidence, onset when supported, confidence, and rainfall context when available.
4. Advice is framed as “inspect/check”; it does not present a causal diagnosis.
5. Synthetic results display a visible banner.

### Officer: record inspection action

**Story:** As an officer, I want to record an inspection status and note so the team can track follow-up.

**Acceptance criteria**

1. An authenticated officer can create an action with status `pending`, `done`, or `needs_expert` and an optional note.
2. The action is associated with the authenticated user and selected field; the server sets timestamps.
3. The user can retrieve their field actions and update a status or note.
4. Invalid status values and unauthorized updates return an explicit API error.

### Farmer: change language and hear an explanation

**Story:** As a smallholder farmer, I want to switch to Marathi or Hindi and hear a short explanation so I can understand what an alert asks me to do.

**Acceptance criteria**

1. The user can select English, Marathi, or Hindi; the chosen language applies to the interface.
2. Translated user-facing strings come from i18n resources; Marathi/Hindi Devanagari renders with the configured fallback font.
3. A read-aloud control reads translated explanation text using browser speech facilities and communicates unavailable speech support.
4. Explanation text describes unusual vegetation behaviour and suggests inspection/checking; it does not diagnose cause.
5. Risk is presented with an icon and text label in every language.

## 5. User journeys

### Officer journey

1. Officer opens the web app and logs in.
2. Officer lands on the dashboard map for the configured region.
3. Officer reviews risk labels, confidence, latest-observation freshness, and any synthetic-data banner.
4. Officer opens an alert field from the map or ranked queue.
5. Officer reads the current result, baseline/time-series evidence, quality flags, onset, and any available rainfall context.
6. Officer visits or otherwise checks the field and records `done`, `pending`, or `needs_expert`, optionally adding a note.

### Farmer journey

1. Farmer opens the field information view.
2. Farmer switches the interface to Marathi or Hindi.
3. Farmer opens the explanation/read-aloud control.
4. Farmer hears or reads a translated, inspection-oriented explanation, with risk and uncertainty visibly labelled.

## 6. Scope

### MVP

- One configured region and one current growing season with historical season-aligned baseline.
- Sentinel-2 NDVI; data retrieval is an offline pipeline operation.
- Cleaning, per-field baseline, anomaly scoring, persistence/onset, confidence, risk classification, and inspection ranking.
- CHIRPS rainfall context if available; its absence does not invalidate NDVI results.
- MongoDB-backed precomputed results; FastAPI JSON API; React map, field detail, queue, action tracking, and methodology page.
- Email/password login with bcrypt and short-lived JWT.
- English, Marathi, and Hindi resource support as required by `AGENTS.md`; these are all part of the MVP, not stretch languages.
- Synthetic demo data with `is_synthetic=true` and a visible banner.
- Browser read-aloud for the farmer explanation.

### Stretch

- Voice input for notes or navigation.
- Additional language(s) beyond English, Marathi, and Hindi.
- A live third-party weather API or richer weather integration beyond configured CHIRPS context.
- Optional Isolation Forest or k-means experiments, only after baseline behavior and validation are complete.
- Additional satellite-sensor support (including Landsat) after sensor harmonisation and validation are defined.

Stretch work must not displace data quality, confidence, auth, synthetic labelling, or the core map/detail/queue flow.

## 7. Success metrics

No results or targets below are asserted as achieved. Collect the metric from the named process and record dataset, method, and run ID. Targets are **to be measured**.

| Metric | Measurement definition | Target/status |
|---|---|---|
| False-alert rate | False alerts per field-season on leave-one-year-out validation, as emitted by `pipeline/validate.py`. | To be measured; no acceptable rate is asserted yet. |
| Detection delay | Delay from injected anomaly onset to first qualifying detection, reported by injection validation. | To be measured; no acceptable delay is asserted yet. |
| Share of fields assessable | Assessable fields divided by all fields in the configured run; report denominator and rules. | To be measured; no target value asserted. |
| Map usability time | Navigation start to field layer and risk labels rendered on seeded data, under the stated acceptance setup. | Target: under 3 seconds; to be measured and recorded. |
| Route/test coverage | Number of backend routes with at least one passing route test divided by total routes. | To be measured; acceptance is every route has at least one test. |
| Locale completeness | Required user-visible keys translated and checked for `en`, `mr`, and `hi`. | To be measured; no percentage result claimed. |
| Inspection-action completion | Count/share of actions moved to `done` or `needs_expert` within a pilot period, segmented by status. | To be measured during pilot; not a model-accuracy claim. |

Validation metrics must come only from `pipeline/validate.py`; never infer true field outcomes from product activity metrics.

## 8. Competitive landscape and differentiation hypothesis

The names below were supplied as comparison candidates, but no product source material or version identifiers were supplied. Consequently, competitor capabilities are **not verified** here. This table is a research checklist, not a claim that a competitor lacks a feature. CropShield entries describe intended MVP requirements, not shipped or independently validated capabilities.

| Product/comparison | Per-field baseline | Persistence | Confidence | Rain context | Explainability | Local language |
|---|---|---|---|---|---|---|
| AgriPulse | Not verified; validate product/version and public evidence. | Not verified. | Not verified. | Not verified. | Not verified. | Not verified. |
| AgroSense-AI | Not verified; validate product/version and public evidence. | Not verified. | Not verified. | Not verified. | Not verified. | Not verified. |
| pymapee | Not verified; identity/scope and public evidence need confirmation. | Not verified. | Not verified. | Not verified. | Not verified. | Not verified. |
| Plain NDVI viewing | No field-specific historical baseline is implied by displaying an NDVI layer alone. | No persistence is implied by a single/current layer. | No confidence estimate is implied. | No rainfall context is implied. | Displays index values; anomaly explanation is not implied. | Depends on viewer; not established by plain NDVI itself. |
| CropShield AI (intended MVP) | Per-field historical baseline planned. | Persistence and onset planned. | Confidence value/label planned. | CHIRPS context when available. | Baseline, time series, quality, onset, thresholds, and limitations planned. | English, Marathi, Hindi planned. All capabilities remain to be implemented and evaluated. |

### Differentiation hypothesis

CropShield may be more useful for an inspection workflow if it combines field-specific history, persistence, explicit confidence, rainfall context, readable evidence, and local-language explanations in one experience. Validate both capability and usability with officers and farmers; do not claim superiority before evidence exists.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Clouds, data gaps, or stale acquisitions yield weak evidence. | Preserve quality flags and freshness; use `cannot_assess` where warranted; expose latest observation date. |
| NDVI anomaly is misread as diagnosis or crop failure. | Use cautious copy, show evidence/limitations, avoid causal language, and test translations with local-language reviewers. |
| Synthetic demo output is mistaken for a real alert. | Carry `is_synthetic=true` through storage/API and show a persistent visible UI banner. |
| Weak field boundaries mix crops or non-crop pixels. | Validate boundaries, expose boundary provenance, report invalid geometry, and treat resulting confidence carefully. |
| No labels make accuracy claims unsupported. | Use only measured leave-one-year-out and injection metrics; label synthetic validation; seek field validation for ground truth. |
| Earth Engine credentials or JWT secrets leak. | Keep secrets out of Git/frontend/logs; use restricted service account and protected environment/secret store. |
| Network/API/DB failure appears as “no alerts.” | Surface loading/error states; distinguish empty from unavailable; never return success-shaped defaults. |
| Scope expands before the core flow is reliable. | Freeze features at the planned point; defer voice, extra languages, optional models, and live weather integrations first. |
| Competitive assumptions are wrong. | Confirm competitor identity and capabilities from current primary product documentation before making comparative claims. |

## 10. Open questions

1. Which exact district/region and authoritative field-boundary source will the pilot use?
2. Which crops and planting calendar apply to that region, and does the default rabi season window fit?
3. What is the operational authority for thresholds and who approves changes to `pipeline/config.py`?
4. How should farmer access differ from officer access to field results and action notes?
5. Which user-facing definition of confidence is understandable without implying probability of crop failure?
6. Which read-aloud voices are available on pilot devices and in Marathi/Hindi?
7. What data-retention and privacy policy applies to user accounts and inspection notes?
8. How will field visits provide ground truth for evaluating false alerts and missed events?
9. What exact products/versions are intended by AgriPulse, AgroSense-AI, and pymapee?
10. Is Landsat support required for the initial pilot, or is Sentinel-2 the chosen source?
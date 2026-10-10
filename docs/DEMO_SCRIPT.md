# CropShield AI: three-minute demo

## Before presenting

- Start MongoDB, the backend, and the frontend; check `/api/health`.
- Load the synthetic demo dataset into a disposable database and sign in with a
  demo account.
- Verify the synthetic-data banner is visible. Never present synthetic records
  as field measurements.
- Check the live ML status and model card. The current checkout has no active
  model, so do not promise a live model result or a usable sensitivity control.
  If the service is unavailable, show the saved baseline evidence and describe
  the unavailable state plainly; do not substitute a test fixture as a real
  model prediction.
- Replace bracketed placeholders only with values visible in the live app or
  emitted by the current pipeline/validation run. If no value is available,
  leave it blank or say it is not yet computed.

## Live walkthrough

### 0:00–0:25 — Sign in and set context

Sign in, and say: “CropShield AI is an early-warning aid. It highlights unusual
vegetation behaviour for inspection; it cannot identify the cause or confirm
crop failure.”

Point out the synthetic-data banner. Say: “This demonstration uses synthetic
data: [synthetic status shown by the app].”

### 0:25–0:55 — Dashboard and map

Show the dashboard and map. Read the current displayed counts without rounding
or embellishing: “The current view shows [field count], [alert count] alerts,
[watch count] watch items, and [cannot-assess count] fields that cannot be
assessed.” If a count is unavailable, skip it.

Explain: “The map links each field boundary with its latest current-season
result. Risk is shown with labels and icons as well as map styling.”

### 0:55–1:20 — Choose an alert

Open an alert from “Top fields to inspect.” Read the field identifier and risk
label shown on screen: “[field name or ID], [risk and severity].”

Say: “This ranking helps prioritize inspection. It is not a diagnosis or a claim
that crop loss occurred.”

If an approved, enabled model card is available, show its model-result card,
model version and any genuinely provided factors. Otherwise state that the
model remains gated and that this screen is showing the stored pipeline result,
not a live model prediction.

### 1:20–1:55 — Evidence and chart

Point to the observed NDVI curve, the baseline median, the uncertainty band, and
the latest observation. Read only values rendered for this field: “The chart
shows [observation date], [observed NDVI], and [baseline/band values if
available]. The alert evidence is [evidence visible in the app].”

Explain: “Cloud-affected observations are quality-checked, and interpolated
points are not used to trigger alerts. Rainfall is contextual evidence, not
proof of a cause.”

Show the sensitivity preview and regional what-if counts only if the active
model card permits a threshold override. Keep the “Preview only, not saved”
label visible. If the card does not permit it or ML is unavailable, leave the
control disabled/hidden and continue with the stored result.

### 1:55–2:20 — Marathi and read-aloud

Switch the language to Marathi. Confirm the visible labels update. Use the
read-aloud control if a Marathi speech voice is available; otherwise use the
text fallback and explain that voice availability depends on the browser/device.

### 2:20–2:40 — Inspection action

Record an inspection action with status `done` and a neutral note such as
“Field checked; follow-up recorded.” Refresh and show that the action remains.
Do not write an unverified diagnosis in the note.

### 2:40–3:00 — Methodology and close

Open Methodology. Point to the effective thresholds and validation report as
returned by the selected run. Say: “Validation values are shown only when
computed. Synthetic anomaly injection does not establish real-world detection
accuracy.”

Close: “The system helps teams decide where to inspect next. Human field
verification remains necessary.”

## Fallback

Before the session, rehearse the ML cold-start path: make one warmup request,
show the waking status/countdown, and wait for readiness. The service's model
load duration is not measured for an approved model; do not promise a startup
time. If it does not become ready, demonstrate that precomputed dashboard,
map, queue, charts, and Methodology remain available, and omit live scoring.

If live MongoDB or network access is unavailable, use a pre-recorded run of the
same synthetic demo and clearly identify it as recorded synthetic data. If the
UI is unavailable, show the checked-in architecture and explain the pipeline,
API, and frontend responsibilities without inventing metrics. Do not substitute
made-up numbers or imply the demo data is real.

## Judge Q&A

**How is this different from plain NDVI viewing?**  
It compares current observations with a field/cluster seasonal baseline, accounts
for observation quality and persistence, adds rainfall context, and ranks fields
for inspection. It is an aid to review, not a replacement for imagery or field
checks.

**Why not use deep learning?**  
This project has no curated, representative ground-truth labels for supervised
training. The current pipeline result remains the only supported risk decision.
The audited nested model is not a crop-stress detector and is not enabled for
risk scoring.

**How are clouds handled?**  
The extraction uses Cloud Score+ masking and tracks valid-pixel fraction.
Low-quality observations remain available for confidence/context but do not
trigger risk. Missing or stale evidence can lead to `cannot_assess`; NaN values
are not treated as zero.

**Can NDVI identify the cause of unusual vegetation behaviour?**  
No. It cannot establish pests, drought, disease, or any other cause. An alert
means the field should be inspected.

**How is it validated without ground truth?**  
The pipeline can report leave-one-year-out checks and synthetic anomaly
injection metrics. Synthetic injection evaluates the pipeline under the
injection assumptions only; it is not real-world accuracy. A field study with
verified outcomes is needed for that.

**What are the limitations?**  
Cloud cover, revisit intervals, mixed pixels, boundary quality, crop/season
variation, baseline coverage, and the absence of verified labels all affect
reliability. Low confidence, stale data, and insufficient clear observations
must be treated cautiously. Users should inspect/check fields and follow local
expert guidance.

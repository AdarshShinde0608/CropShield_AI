# Sustainability and responsible operation

## Current evidence

CropShield AI is a work-in-progress prototype. No environmental impact,
compute-energy use, water use, avoided travel, or emissions have been measured.
No sustainability benefit is claimed.

The workflow is designed around offline, seasonal processing and precomputed
results. The optional ML service is currently gated because there is no active
approved artifact under `models/`; no production model inference is running.
Synthetic fixtures and demo data are not operational or environmental evidence.

## Operating principles

- Process only the current-season observations and supporting evidence needed
  by the documented workflow.
- Keep live inference optional so dashboard, map, queue, and chart views can use
  stored results when the service is unavailable.
- Avoid unnecessary reprocessing by recording run configuration and artifact
  versions with each analysis.
- Keep raw and processed input data local and access-controlled; do not retain
  unnecessary farmer, field, or location data.
- Use the lowest compute tier that has been measured to meet reliability and
  memory needs. No native service dependency size, loaded-model footprint, or
  inference latency has been measured for this release.
- Keep the Render services optional and allow free-instance sleep/cold starts
  to affect live previews only; persisted dashboard, map, and chart results
  must remain available through the backend.
- Validate the alert workflow with local agricultural experts and field
  observations before claiming it avoids travel or improves resource use.

## Evaluation questions

For any future pilot, record processing frequency, input volume, compute
duration and infrastructure, data-retention period, and the human actions
resulting from an alert. Compare any claimed travel or resource savings against
a defined baseline. Report methodology and uncertainty; do not infer avoided
field visits, yield protection, or emissions reduction from map usage alone.

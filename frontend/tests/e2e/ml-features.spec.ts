import { expect, test, type Page } from "@playwright/test";

const modelCard = {
  enabled: true,
  model_version: "fixture-v1",
  name: "Fixture vegetation model",
  task: "field-level vegetation signal mapping",
  training_data: "Not measured in this fixture",
  measured_metrics: null,
  limitations: ["Fixture metadata only"],
  licence: "Fixture licence",
  attribution: "Fixture attribution",
  output_specification: {
    decision_threshold: { minimum: 0.1, maximum: 0.9, default: 0.5 }
  }
};

async function preparePage(
  page: Page,
  options: {
    statuses?: Array<{ body: unknown; code: number }>;
    scorePreview?: { body: unknown; code: number };
  } = {}
) {
  const statuses = options.statuses ?? [
    { body: { status: "ready", model_version: "fixture-v1" }, code: 200 }
  ];
  let statusIndex = 0;
  await page.addInitScript(() => localStorage.setItem("cropshield.access_token", "fixture-token"));
  await page.route((url) => new URL(url).pathname.startsWith("/api/"), async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });

    if (path.endsWith("/auth/me")) {
      return json({ id: "user-1", email: "fixture@example.test", name: "Fixture User", role: "officer", language: "en" });
    }
    if (path.endsWith("/ml/warmup")) return json({ status: "accepted" }, 202);
    if (path.endsWith("/ml/status")) {
      const response = statuses[Math.min(statusIndex, statuses.length - 1)];
      statusIndex += 1;
      return json(response.body, response.code);
    }
    if (path.endsWith("/model-info")) return json(modelCard);
    if (path.endsWith("/fields/field-1/score-preview")) {
      const preview = options.scorePreview ?? {
        body: {
        field_id: "field-1",
        risk: "alert",
        severity: "moderate",
        confidence: null,
        confidence_label: null,
        model_score: 0.7,
        top_factors: null,
        evidence: { observations: [] },
        drop_start: null,
        rain_context: "not_applicable",
        model_version: "fixture-v1",
        decision_threshold: 0.6,
        preview: true
        },
        code: 200
      };
      return json(preview.body, preview.code);
    }
    if (path.endsWith("/regions/region-1/score-preview")) {
      return json({
        region_id: "region-1",
        preview: true,
        total_fields: 2,
        scored_fields: 2,
        counts_by_risk: { normal: 1, watch: 0, alert: 1, cannot_assess: 0 }
      });
    }
    if (path.endsWith("/fields/field-1/timeseries")) {
      return json({
        field_id: "field-1",
        drop_start: "2026-01-10",
        points: [{
          date: "2026-01-10",
          ndvi: 0.42,
          baseline_median: 0.65,
          band_low: 0.5,
          band_high: 0.8,
          z: -1.2,
          low_quality: false,
          is_interpolated: false
        }],
        rainfall: []
      });
    }
    if (path.endsWith("/fields/field-1")) {
      return json({
        field_id: "field-1",
        risk: "watch",
        severity: null,
        confidence: 0.6,
        confidence_label: "medium",
        z_score: -1.2,
        pct_below_normal: 12,
        drop_start: "2026-01-10",
        latest_obs_date: "2026-01-10",
        n_valid_obs: 5,
        baseline_years: 3,
        rain_context: "normal",
        advice_key: null,
        advice: null,
        priority_score: 0.5,
        priority_rank: 1,
        if_flag: null,
        is_synthetic: false,
        model_version: "fixture-v1",
        model_score: 0.55,
        top_factors: ["low vegetation index"],
        evidence: {
          observations: [{
            date: "2026-01-10",
            ndvi: 0.42,
            baseline_median: 0.65,
            baseline_lower: 0.5,
            baseline_upper: 0.8,
            is_clear: true
          }]
        }
      });
    }
    if (path.endsWith("/methodology")) {
      return json({
        run_id: null,
        params: {},
        method_steps: [],
        validation_report: null,
        limitations: [],
        created_at: null
      });
    }
    if (path.endsWith("/regions")) {
      return json([{ region_id: "region-1", name: "Fixture region", state: "Maharashtra", latest_run_id: null, latest_observation_date: null, is_synthetic: false }]);
    }
    if (path.endsWith("/regions/region-1/summary")) {
      return json({
        region_id: "region-1",
        counts_by_risk: { normal: 1, watch: 1, alert: 0, cannot_assess: 0 },
        latest_observation_date: "2026-01-10",
        run_id: "run-1",
        is_synthetic: false
      });
    }
    if (path.endsWith("/regions/region-1/fields")) {
      return json({
        type: "FeatureCollection",
        features: [{
          type: "Feature",
          geometry: {
            type: "Polygon",
            coordinates: [[[73.8, 18.5], [73.81, 18.5], [73.81, 18.51], [73.8, 18.51], [73.8, 18.5]]]
          },
          properties: {
            field_id: "field-1",
            name: "Fixture field",
            risk: "alert",
            severity: "moderate",
            confidence: 0.7,
            confidence_label: "medium",
            z_score: -1.2,
            pct_below_normal: 12,
            drop_start: "2026-01-10",
            latest_obs_date: "2026-01-10",
            n_valid_obs: 5,
            baseline_years: 3,
            rain_context: "normal",
            advice_key: null,
            advice: null,
            priority_score: 0.5,
            priority_rank: 1,
            if_flag: null,
            is_synthetic: false
          }
        }]
      });
    }
    if (path.endsWith("/regions/region-1/queue")) {
      return json([{
        field_id: "field-1",
        name: "Fixture field",
        risk: "alert",
        severity: "moderate",
        confidence_label: "medium",
        latest_obs_date: "2026-01-10",
        priority_rank: 1,
        is_synthetic: false
      }]);
    }
    return json({ detail: "Unexpected fixture request", code: "NOT_FOUND" }, 404);
  });
}

test("field detail shows saved model evidence and a non-persistent sensitivity preview", async ({ page }) => {
  const thresholds: number[] = [];
  await preparePage(page);
  page.on("request", (request) => {
    if (request.url().endsWith("/fields/field-1/score-preview")) {
      thresholds.push(request.postDataJSON().decision_threshold);
    }
  });

  await page.goto("/fields/field-1");
  await expect(page.getByRole("heading", { name: "Model result" })).toBeVisible();
  await expect(page.getByText("Model version fixture-v1")).toBeVisible();
  await expect(page.getByText("low vegetation index")).toBeVisible();
  await expect(page.getByText("Evidence-based onset date")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sensitivity (what-if)" })).toBeVisible();
  await expect(page.getByText("Preview only, not saved")).toBeVisible();
  await expect(page.getByText("With these settings")).toBeVisible();
  await expect.poll(() => thresholds.length).toBeGreaterThan(0);
});

test("dashboard what-if drawer shows region risk counts", async ({ page }) => {
  await preparePage(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Region what-if" }).click();
  await expect(page.getByRole("dialog", { name: "Region what-if" })).toBeVisible();
  await expect(page.getByText("Preview only, not saved")).toBeVisible();
  await expect(page.getByText("2 of 2 fields scored in this preview.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Close region sensitivity panel" })).toBeVisible();
});

test("methodology shows model-card details without inventing evaluation metrics", async ({ page }) => {
  await preparePage(page);
  await page.goto("/methodology");
  await expect(page.getByRole("heading", { name: "About the model" })).toBeVisible();
  await expect(page.getByText("Fixture vegetation model")).toBeVisible();
  await expect(page.getByText("Not yet measured")).toBeVisible();
  await expect(page.getByText("Fixture licence · Fixture attribution")).toBeVisible();
});

test("waking status shows a countdown while precomputed dashboard results remain available", async ({ page }) => {
  let warmupRequests = 0;
  await preparePage(page, { statuses: [{
    body: { detail: { detail: "service is starting", code: "ML_WAKING" } },
    code: 503
  }] });
  page.on("request", (request) => {
    if (request.url().endsWith("/ml/warmup")) warmupRequests += 1;
  });
  await page.goto("/");
  await expect(page.getByRole("status").filter({ hasText: "Analysis engine is waking up" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Analysis engine startup progress" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Regional summary" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Region what-if" })).toHaveCount(0);
  expect(warmupRequests).toBe(1);
});

test("unavailable status hides live controls but keeps precomputed results", async ({ page }) => {
  await preparePage(page, { statuses: [{
    body: { detail: { detail: "service unavailable", code: "ML_UNAVAILABLE" } },
    code: 503
  }] });
  await page.goto("/");
  await expect(page.getByRole("status").filter({ hasText: "Live analysis is temporarily unavailable" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Regional summary" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Region what-if" })).toHaveCount(0);
});

test("slow wake recovers and re-enables preview controls", async ({ page }) => {
  await preparePage(page, {
    statuses: [
      { body: { detail: { detail: "service is starting", code: "ML_WAKING" } }, code: 503 },
      { body: { status: "ready", model_version: "fixture-v1" }, code: 200 }
    ]
  });
  await page.goto("/");
  await expect(page.getByRole("status").filter({ hasText: "Analysis engine is waking up" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Regional summary" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Region what-if" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("status").filter({ hasText: "Analysis engine is waking up" })).toHaveCount(0);
});

test("wrong service key makes preview unavailable without exposing secrets", async ({ page }) => {
  let previewHadServiceKey = false;
  await preparePage(page, {
    scorePreview: {
      body: { detail: { detail: "ML service returned an error", code: "ML_UNAVAILABLE" } },
      code: 503
    }
  });
  page.on("request", (request) => {
    if (request.url().endsWith("/fields/field-1/score-preview")) {
      previewHadServiceKey = "X-Service-Key" in request.headers();
    }
  });
  await page.goto("/fields/field-1");
  await expect(page.getByRole("heading", { name: "Sensitivity (what-if)" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "A live preview is unavailable right now" })).toBeVisible();
  await expect(page.getByText(/wrong-service-key-fixture/)).toHaveCount(0);
  expect(previewHadServiceKey).toBe(false);
});

test("backend checksum-mismatch degradation keeps the dashboard usable", async ({ page }) => {
  await preparePage(page, { statuses: [{
    body: { detail: { detail: "ML service unavailable", code: "ML_UNAVAILABLE" } },
    code: 503
  }] });
  await page.goto("/");
  await expect(page.getByRole("status").filter({ hasText: "Live analysis is temporarily unavailable" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Regional summary" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Region what-if" })).toHaveCount(0);
});

test("stopped ML leaves the map, queue, evidence chart, and methodology available", async ({ page }) => {
  await preparePage(page, { statuses: [{
    body: { detail: { detail: "ML service unavailable", code: "ML_UNAVAILABLE" } },
    code: 503
  }] });
  await page.goto("/");
  await expect(page.locator(".leaflet-container")).toBeVisible();
  await expect(page.getByRole("region", { name: "Regional summary" })).toBeVisible();

  await page.goto("/queue");
  await expect(page.getByRole("heading", { name: "Inspection queue" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Fixture field" })).toBeVisible();

  await page.goto("/fields/field-1");
  await expect(page.locator(".recharts-surface").first()).toBeVisible();
  await expect(page.getByText("Vegetation index over time")).toBeVisible();

  await page.goto("/methodology");
  await expect(page.getByRole("heading", { name: "About the model" })).toBeVisible();
});

test("Marathi switch works while ML service is unavailable", async ({ page }) => {
  await preparePage(page, { statuses: [{
    body: { detail: { detail: "ML service unavailable", code: "ML_UNAVAILABLE" } },
    code: 503
  }] });
  await page.goto("/");
  await expect(page.getByRole("status").filter({ hasText: "Live analysis is temporarily unavailable" })).toBeVisible();
  await page.getByRole("combobox", { name: "Language" }).selectOption("mr");
  await expect(page.getByRole("combobox", { name: "भाषा" })).toHaveValue("mr");
  await expect(page.getByText(/थेट विश्लेषण तात्पुरते उपलब्ध नाही/)).toBeVisible();
  await expect(page.getByRole("region", { name: "प्रदेशाचा सारांश" })).toBeVisible();
});

# CropShield AI: System Architecture and File Structure

Single source of truth for the team and for GitHub Copilot. Read this before writing any code.

## 1. Key decisions

| Area | Decision | Why |
|---|---|---|
| Repo layout | One monorepo with 3 separate deployable parts: `frontend/`, `backend/`, `pipeline/` | Frontend and backend are fully separate; the ML/GEE pipeline is kept out of the web server |
| Frontend | React + Vite + TypeScript, Tailwind, React Router, TanStack Query, Axios, react-leaflet, Recharts, i18next | Fast to build, matches the UXPilot design export |
| Backend | Python 3.11+, FastAPI, Pydantic v2, Motor (async MongoDB driver), PyJWT, bcrypt | Async, typed, auto docs at `/docs` |
| Database | MongoDB Atlas in production; locally installed MongoDB or a separate Atlas development database | Fits GeoJSON fields and time series |
| Auth | Email + password, bcrypt hash, JWT bearer access token | Requested; simple and standard |
| CORS | FastAPI `CORSMiddleware`, allowed origins from env var | Frontend and backend on different origins |
| Earth Engine | Used only by `pipeline/`, with a **service account JSON key** | See note below |
| ML | Statistical anomaly pipeline in pandas (robust z-score, persistence, confidence) plus optional k-means and Isolation Forest | No ground-truth labels, so no supervised model |

**Important correction on the "Earth Engine API key":** Earth Engine does not use a simple API key. Server-side access uses a Google Cloud project registered for Earth Engine plus a **service account** and its JSON key file. Keep that key only in `pipeline/` environment variables or a secret manager. Never put it in the frontend, never in the backend web server, never in Git.

## 2. Architecture

```
                        OFFLINE (run on a developer machine or a scheduled job)
 +------------------------------------------------------------------------------+
 |  Google Earth Engine  --->  pipeline/ (Python, pandas, scikit-learn)         |
 |  Sentinel-2, CHIRPS,        extract -> clean -> baseline -> score ->         |
 |  WorldCover                 context -> confidence -> risk -> validate        |
 |                                          |                                   |
 |                                          v  load_to_mongo.py                 |
 +------------------------------------------|-----------------------------------+
                                            v
                                   +------------------+
                                   |     MongoDB      |
                                   +--------^---------+
                                            |  Motor
                        ONLINE              |
 +-----------------------------+   +--------+---------+
 |  frontend/ (React, Vite)    |   | backend/ FastAPI |
 |  Login, Dashboard map,      |-->| JWT auth, CORS,  |
 |  Field detail, Queue,       |<--| read APIs,       |
 |  Methodology, i18n          |   | actions API      |
 +-----------------------------+   +------------------+
        HTTPS + Bearer JWT
```

**Why batch, not live:** Earth Engine calls are slow and quota-limited. Precomputing results into MongoDB makes the demo fast and reliable, and means the web backend never holds Earth Engine credentials.

### Component responsibilities

| Component | Does | Does NOT |
|---|---|---|
| `pipeline/` | Pulls GEE data, runs the ML pipeline, validates, writes results to MongoDB | Serve HTTP, handle users |
| `backend/` | Auth, serve results, store user actions, expose methodology and metrics | Call Earth Engine, recompute scores |
| `frontend/` | UI, map, charts, language, read-aloud | Hold secrets, compute risk |
| MongoDB | Stores users, fields, observations, results, actions | Store satellite pixels |

## 3. Shared constants (defined once in `pipeline/config.py`)

These must match everywhere. Note: day-of-season (DOS) counts from **1 November**, to match the extraction script (not 1 October).

| Constant | Value |
|---|---|
| Season window | 1 Nov to 31 Mar (rabi) |
| Baseline seasons | 2019-20 to 2024-25 |
| Current season | 2025-26 |
| `MIN_VALID_FRAC` | 0.5 |
| `SPIKE_DELTA` | 0.2 |
| `MAX_INTERP_GAP_DAYS` | 20 |
| `DOS_WINDOW` | 12 days |
| `MIN_BASELINE_YEARS` | 3 |
| `SIGMA_FLOOR` | 0.05 |
| `Z_WATCH` | -1.5 |
| `Z_HIGH` | -2.0 |
| `DEV_HIGH_PCT` | 20 |
| `STALE_DAYS` | 20 |
| `CS_THRESHOLD` (cloud score) | 0.6 |

All are starting values to be tuned. They are saved with each analysis run and shown on the Methodology page.

## 4. Risk vocabulary (used identically in pipeline, API and UI)

| Field | Allowed values |
|---|---|
| `risk` | `normal`, `watch`, `alert`, `cannot_assess` |
| `severity` (only when `risk=alert`) | `moderate`, `high` |
| `confidence_label` | `high`, `medium`, `low` |
| `confidence` | float 0 to 1 |

## 5. MongoDB collections

| Collection | Key fields | Indexes |
|---|---|---|
| `users` | `email`, `password_hash`, `name`, `role` (`officer`/`farmer`), `language`, `created_at` | unique `email` |
| `regions` | `name`, `state`, `bbox`, `centroid` | none |
| `fields` | `region_id`, `field_id`, `name`, `geometry` (GeoJSON Polygon), `area_ha`, `is_synthetic_boundary`, `cluster` | `2dsphere` on `geometry`; `region_id`; unique `field_id` |
| `seasons` | `season_id`, `label`, `start`, `end`, `role` (`baseline`/`current`) | unique `season_id` |
| `observations` | `field_id`, `season_id`, `date`, `dos`, `ndvi`, `valid_frac`, `baseline_median`, `baseline_sigma`, `z`, `pct_dev`, `is_interpolated`, `low_quality` | unique `(field_id, season_id, date)` |
| `rainfall` | `region_id`, `date`, `rain_mm`, `rain14`, `rain30`, `rain_z` | `(region_id, date)` |
| `field_results` | `field_id`, `region_id`, `season_id`, `run_id`, `risk`, `severity`, `confidence`, `confidence_label`, `z_score`, `pct_below_normal`, `drop_start`, `latest_obs_date`, `n_valid_obs`, `baseline_years`, `rain_context`, `advice_key`, `advice`, `priority_score`, `priority_rank`, `if_flag` | `(region_id, season_id, priority_rank)` |
| `analysis_runs` | `run_id`, `created_at`, `params` (all constants), `is_synthetic`, `n_fields`, `notes` | unique `run_id` |
| `validation_reports` | `run_id`, `loyo` (false alerts per field-season), `injection` (recall, FAR, delay, F1, per magnitude), `thresholds_sweep` | `run_id` |
| `actions` | `user_id`, `field_id`, `status` (`pending`/`done`/`needs_expert`), `note`, `created_at`, `updated_at` | `(field_id, user_id)` |

## 6. API contract (backend)

Base path `/api`. All endpoints except `health`, `auth/register`, `auth/login`, `methodology` need `Authorization: Bearer <JWT>`.

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{status:"ok"}` |
| POST | `/auth/register` | `{access_token, token_type, user}` |
| POST | `/auth/login` | `{access_token, token_type, user}` |
| GET | `/auth/me` | current user |
| PATCH | `/auth/me` | update `name`, `language` |
| GET | `/regions` | list of regions with latest run info |
| GET | `/regions/{region_id}/summary` | counts by risk, latest observation date, run id, `is_synthetic` flag |
| GET | `/regions/{region_id}/fields` | GeoJSON FeatureCollection; each feature's properties hold the result fields |
| GET | `/regions/{region_id}/queue` | ranked inspection list (query: `risk`, `limit`) |
| GET | `/fields/{field_id}` | full result for one field |
| GET | `/fields/{field_id}/timeseries` | observations, baseline band, rainfall, `drop_start` |
| GET | `/fields/{field_id}/actions` | actions by the current user |
| POST | `/fields/{field_id}/actions` | create an action |
| PATCH | `/actions/{action_id}` | update status or note |
| GET | `/methodology` | thresholds, method steps, validation metrics, limitations |

Example `field_results` feature properties:

```json
{
  "field_id": "F012",
  "risk": "alert",
  "severity": "moderate",
  "confidence": 0.62,
  "confidence_label": "medium",
  "z_score": -2.1,
  "pct_below_normal": 24,
  "drop_start": "2026-01-14",
  "latest_obs_date": "2026-02-08",
  "n_valid_obs": 3,
  "baseline_years": 6,
  "rain_context": "dry_spell",
  "advice": "Check soil moisture and irrigation status in this field.",
  "priority_rank": 3,
  "is_synthetic": false
}
```

Illustrative values only. Real values come from the pipeline.

Timeseries response shape:

```json
{
  "field_id": "F012",
  "drop_start": "2026-01-14",
  "points": [
    {"date": "2026-01-04", "ndvi": 0.51, "baseline_median": 0.58, "band_low": 0.52, "band_high": 0.64, "z": -0.9, "low_quality": false, "is_interpolated": false}
  ],
  "rainfall": [{"date": "2026-01-04", "rain_mm": 0.0, "rain30": 4.2}]
}
```

Error format for all endpoints: `{"detail": "message", "code": "SOME_CODE"}` with correct HTTP status.

## 7. Auth design (JWT)

- Register: validate email format, password at least 8 characters. Hash with bcrypt. Never store or log plain passwords.
- Login: verify hash, return a JWT (HS256) with `sub` = user id, `role`, `exp` = 60 minutes.
- `get_current_user` dependency decodes the token, loads the user, returns 401 when invalid or expired.
- Frontend keeps the token in memory with a `localStorage` backup (hackathon trade-off; httpOnly cookies are safer for production), attaches it via an Axios interceptor, and redirects to `/login` on any 401.
- Seed one demo account for judges (credentials in `.env.example` comments, not in code).
- Rate-limit `/auth/login` if time allows.

## 8. CORS and security

- `CORS_ORIGINS` env var (comma-separated). Never use `*` outside local development.
- Allow methods `GET, POST, PATCH, OPTIONS`; headers `Authorization, Content-Type`; `allow_credentials=False` (bearer tokens, no cookies).
- Validate every input with Pydantic. Use projections so password hashes never leave the DB layer.
- No secrets in Git. `.env.example` has placeholders only.
- Security headers and HTTPS come from the hosting platform.

## 9. Environment variables

`backend/.env.example`
```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=cropshield
JWT_SECRET=change-me-long-random
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:5173
```

`pipeline/.env.example`
```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=cropshield
GEE_PROJECT=your-gcp-project-id
GEE_SERVICE_ACCOUNT=your-sa@your-project.iam.gserviceaccount.com
GEE_KEY_FILE=./secrets/gee-key.json
```

`frontend/.env.example`
```
VITE_API_BASE_URL=http://localhost:8000/api
```

## 10. Repository structure

```
cropshield-ai/
├── AGENTS.md                      # rules for AI coding agents (also read by Copilot)
├── README.md
├── .python-version                # pinned Python runtime for local development and Render
├── scripts/
│   ├── dev.ps1                    # start backend, ML service, and frontend on Windows
│   ├── dev.sh                     # start backend, ML service, and frontend on macOS/Linux
│   └── fetch_model.py             # build-time HTTPS artifact verification
├── .gitignore
├── .github/
│   └── copilot-instructions.md    # short pointer to AGENTS.md
├── docs/
│   ├── SRS.md
│   ├── PRD.md
│   ├── TECHNICAL_ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── BUSINESS_MODEL_CANVAS.md
│   ├── API_CONTRACT.md
│   ├── DATA_DICTIONARY.md
│   └── DEMO_SCRIPT.md
│
├── backend/
│   ├── app/
│   │   ├── main.py                # app factory, CORS, routers, lifespan (DB connect)
│   │   ├── core/
│   │   │   ├── config.py          # pydantic-settings
│   │   │   ├── security.py        # bcrypt, JWT create/verify
│   │   │   ├── database.py        # Motor client, index creation
│   │   │   └── errors.py          # exception handlers, error format
│   │   ├── api/
│   │   │   ├── deps.py            # get_db, get_current_user
│   │   │   └── routes/
│   │   │       ├── health.py
│   │   │       ├── auth.py
│   │   │       ├── regions.py
│   │   │       ├── fields.py
│   │   │       ├── actions.py
│   │   │       └── methodology.py
│   │   ├── schemas/               # Pydantic request/response models
│   │   │   ├── auth.py
│   │   │   ├── field.py
│   │   │   ├── result.py
│   │   │   ├── timeseries.py
│   │   │   └── action.py
│   │   ├── services/              # business logic, DB queries
│   │   │   ├── auth_service.py
│   │   │   ├── region_service.py
│   │   │   ├── field_service.py
│   │   │   └── action_service.py
│   │   └── utils/
│   │       └── geojson.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_regions_fields.py
│   │   └── test_actions.py
│   ├── requirements.in
│   ├── requirements.txt           # pinned dependency lock
│   ├── .env.example
│   └── tests/
│
├── pipeline/                      # offline: Earth Engine + ML. Never imported by backend.
│   ├── config.py                  # ALL constants (section 3)
│   ├── ee_extract.py              # Earth Engine pull (service account auth)
│   ├── clean.py                   # steps 1-2: cleaning, DOS, regularise
│   ├── baseline.py                # step 3-4: baseline, sigma shrinkage, k-means
│   ├── score.py                   # steps 5-7: z, pct dev, persistence, onset, ranking
│   ├── context.py                 # step 8, 12: rain context, advice lookup
│   ├── confidence.py              # step 9
│   ├── iforest.py                 # step 10 (optional)
│   ├── validate.py                # leave-one-year-out, injection, threshold sweep
│   ├── run_pipeline.py            # runs everything, writes processed outputs
│   ├── load_to_mongo.py           # writes fields, observations, results, runs to MongoDB
│   ├── seed_demo.py               # SYNTHETIC demo data (labelled is_synthetic=true)
│   ├── data/
│   │   ├── raw/                   # ndvi_YYYY_YYYY.csv, rain_YYYY_YYYY.csv, fields.geojson
│   │   └── processed/
│   ├── tests/
│   │   ├── test_clean.py
│   │   ├── test_baseline.py
│   │   ├── test_score.py
│   │   └── test_confidence.py
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── tsconfig.json
    ├── .env.example
    └── src/
        ├── main.tsx
        ├── App.tsx                # router + providers
        ├── api/
        │   ├── client.ts          # Axios instance, auth interceptor, 401 handling
        │   ├── auth.ts
        │   ├── regions.ts
        │   ├── fields.ts
        │   └── actions.ts
        ├── auth/
        │   ├── AuthContext.tsx
        │   └── ProtectedRoute.tsx
        ├── pages/
        │   ├── LoginPage.tsx
        │   ├── RegisterPage.tsx
        │   ├── DashboardPage.tsx
        │   ├── FieldDetailPage.tsx
        │   ├── QueuePage.tsx
        │   ├── MethodologyPage.tsx
        │   └── NotFoundPage.tsx
        ├── components/
        │   ├── layout/            # AppShell, Sidebar, TopBar, MobileTabBar
        │   ├── map/               # RiskMap, MapLegend, FieldPopup
        │   ├── charts/            # NdviChart, RainfallBars
        │   ├── field/             # RiskBadge, ConfidenceMeter, EvidenceList, AdvicePanel, ActionTracker
        │   └── common/            # KpiCard, Skeleton, EmptyState, ErrorState, SyntheticBanner, LanguageSwitcher, ReadAloudButton
        ├── i18n/
        │   ├── index.ts
        │   └── locales/{en.json, mr.json, hi.json}
        ├── hooks/                 # useRegionFields, useFieldDetail, useTimeseries, useSpeech
        ├── types/                 # api.ts (mirrors section 6)
        ├── lib/                   # riskStyles.ts, format.ts
        └── styles/index.css
```

## 11. Deployment

| Part | Host | Notes |
|---|---|---|
| Frontend | Vercel or Netlify | set `VITE_API_BASE_URL` |
| Backend | Render, Railway or Fly.io | set env vars, start with `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Database | MongoDB Atlas free tier | allow the backend host's IPs |
| Pipeline | Developer laptop | run once, then `load_to_mongo.py` against Atlas |

## 12. Honest-scope rules (carry into UI copy and docs)

- An alert means "unusual vegetation behaviour", not confirmed crop damage and not a probability of failure.
- NDVI cannot identify the cause (drought, pests, disease, nutrients, late sowing).
- Synthetic data and synthetic validation must be visibly labelled.
- Never show a metric that was not measured.

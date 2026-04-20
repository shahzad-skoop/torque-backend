# Torque Backend

Production FastAPI backend for the Torque intelligence platform.

- **Production API:** <https://api.usetorque.co>
- **Interactive docs (Swagger UI):** <https://api.usetorque.co/docs>
- **OpenAPI JSON:** <https://api.usetorque.co/openapi.json>
- **ReDoc:** <https://api.usetorque.co/redoc>

---

## Table of contents

1. [Stack](#stack)
2. [Architecture](#architecture)
3. [Deployment topology](#deployment-topology)
4. [Background jobs](#background-jobs)
5. [API reference](#api-reference)
   - [Health](#health)
   - [Auth](#auth)
   - [Footprints](#footprints)
   - [Analysis](#analysis)
6. [Local development](#local-development)
7. [Production operations](#production-operations)
8. [CI / CD](#ci--cd)
9. [Implemented vs scaffolded](#implemented-vs-scaffolded)

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI (Python 3.13) |
| Queue | Celery + Redis |
| DB | PostgreSQL 16 + PostGIS |
| Object storage | MinIO (S3 compatible) |
| Migrations | Alembic |
| Tests / lint | pytest + Ruff |
| Container runtime | Docker / Compose |
| CI / CD | GitHub Actions → GHCR |
| Auto-deploy | Watchtower (server) |
| Ingress | Cloudflare Tunnel → `api.usetorque.co` |

---

## Architecture

```
                            Cloudflare Tunnel
                                    │
                                    ▼
                   ┌────────────────────────────────┐
                   │   torque-backend-api (FastAPI) │
                   │   127.0.0.1:18080 → :8000      │
                   └──┬──────────────┬──────────────┘
                      │              │
          Celery ─────┘              └───── SQLAlchemy / psycopg2
          (redis broker)                         │
                      │                          ▼
                      ▼                ┌────────────────┐
           ┌────────────────────┐      │ torque-postgres│ (PostGIS)
           │ torque-backend-    │      └────────────────┘
           │     worker         │
           │ (Celery worker)    │      ┌────────────────┐
           └─────────┬──────────┘      │ torque-minio   │ (S3 API)
                     │                 └────────────────┘
                     ▼
             ┌────────────────┐
             │ torque-redis   │ (broker + result backend)
             └────────────────┘
```

All three shared infra containers (`torque-postgres`, `torque-redis`, `torque-minio`) run **outside** this repo's compose stack, on shared Docker networks (`edge`, `db`, `object`). The backend joins them as external networks.

---

## Deployment topology

| Container | Image | Role |
|---|---|---|
| `torque-backend-api` | `ghcr.io/shahzad-skoop/torque-backend:prod` | FastAPI + Alembic migrations on boot |
| `torque-backend-worker` | `ghcr.io/shahzad-skoop/torque-backend:prod` | Celery worker (no beat yet in prod) |
| `infra-watchtower` | `containrrr/watchtower` | Pulls the `:prod` tag when GHCR is updated |
| `torque-postgres` | `postgis/postgis:16-3.4` | Primary DB |
| `torque-redis` | `redis:7.4-alpine` | Broker + result backend |
| `torque-minio` | `minio/minio` | Artifact storage (S3-compat) |

See [`deploy/compose.yml`](./deploy/compose.yml) for the server stack and [`.github/workflows/docker-publish.yml`](./.github/workflows/docker-publish.yml) for the publish pipeline.

---

## Background jobs

The backend runs **two classes** of background work on top of Celery + Redis.

### 1. Celery worker — `torque-backend-worker`

Consumes tasks from Redis queue `0` (`CELERY_BROKER_URL`) and writes results to Redis queue `1` (`CELERY_RESULT_BACKEND`). Started with:

```bash
celery -A app.celery_app.celery_app worker --loglevel=INFO
```

Registered tasks:

| Task | Trigger | Purpose |
|---|---|---|
| `app.tasks.analysis_tasks.run_analysis_pipeline` | Enqueued by `POST /api/v1/analysis/runs` | Runs the (currently simulated) satellite-analysis pipeline for a given `AnalysisRun`. Writes `AnalysisRunEvent` rows step-by-step and finally persists an `AnalysisReport`. |
| `app.tasks.analysis_tasks.emit_heartbeat` | Scheduled by Celery Beat (see below) | No-op heartbeat that proves the beat scheduler and worker are alive. Returns `{"status": "ok"}`. |

The pipeline runs these ordered steps and emits a `AnalysisRunEvent` row after each — clients can consume this timeline via the SSE stream endpoint:

```
validate → footprint → weather → night_lights → optical → scores → finalize
```

Current behavior is deterministic-with-jitter simulation; swap out the body of `run_analysis_pipeline` when wiring real providers (Earth Engine, VIIRS, Landsat, Sentinel, weather, trends, etc.).

### 2. Celery Beat — periodic scheduler

Configured in `app/celery_app.py`:

```python
beat_schedule={
    "sample-daily-heartbeat": {
        "task": "app.tasks.analysis_tasks.emit_heartbeat",
        "schedule": 3600.0,  # seconds — currently hourly
    },
}
```

> **Note on production:** the server compose (`deploy/compose.yml`) currently runs only the `api` and `worker` services. If you want the heartbeat schedule firing in production, add a `beat` service to `deploy/compose.yml` running:
> ```bash
> celery -A app.celery_app.celery_app beat --loglevel=INFO
> ```
> Not enabled by default because there are no user-visible periodic jobs yet; the heartbeat is a readiness placeholder.

### 3. Watchtower — auto image rollout

Not a Celery job, but worth mentioning: `infra-watchtower` polls GHCR every 60s for a new digest of `:prod` and recreates the API and worker containers in place when a new image is published. Both carry the label `com.centurylinklabs.watchtower.enable=true`.

### Inspecting jobs in prod

```bash
# See what the worker is doing right now
docker logs -f torque-backend-worker

# Count active / reserved / scheduled tasks
docker exec torque-backend-worker celery -A app.celery_app.celery_app inspect active
docker exec torque-backend-worker celery -A app.celery_app.celery_app inspect reserved
docker exec torque-backend-worker celery -A app.celery_app.celery_app inspect scheduled

# Ping the worker from outside
docker exec torque-backend-worker celery -A app.celery_app.celery_app inspect ping
```

---

## API reference

All endpoints are under the `/api/v1` prefix. Open <https://api.usetorque.co/docs> for live Swagger UI with schemas, example payloads, and a "Try it out" console.

### Health

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness. Returns app name + environment. Never hits the DB. |
| GET | `/api/v1/health/ready` | Readiness. Executes `SELECT 1` on Postgres. Used by the container healthcheck. |

**Examples**

```bash
curl -s https://api.usetorque.co/api/v1/health
# {"status":"ok","service":"Torque Backend","environment":"production"}

curl -s https://api.usetorque.co/api/v1/health/ready
# {"status":"ready"}
```

---

### Auth

Thin wrapper over the Skoop auth-service (or a local mock when `AUTH_MOCK_MODE=true`). On successful login/signup, a `torque_session` cookie is set with `HttpOnly`, `Secure`, and `SameSite=Lax` (configurable via `SESSION_COOKIE_SECURE` / `SESSION_COOKIE_SAMESITE`).

#### `POST /api/v1/auth/login`

Request body (`LoginRequest`):

```json
{
  "email": "user@example.com",
  "password": "password-min-8-chars"
}
```

Response (`AuthTokenResponse`):

```json
{
  "token": "<opaque-token>",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

Also sets `Set-Cookie: torque_session=<token>; HttpOnly; Secure; SameSite=Lax; Max-Age=86400`.

Errors: `502 Bad Gateway` if the upstream auth service is unreachable.

#### `POST /api/v1/auth/signup`

Request body (`SignupRequest`):

```json
{
  "email": "user@example.com",
  "password": "password-min-8-chars",
  "first_name": "Jane",
  "last_name": "Doe",
  "environment": "production",
  "meta_data": { "source": "web" }
}
```

Response: same shape as login.

---

### Footprints

RDC / distribution-center footprint model. Data is loaded via `python -m scripts.seed_rdc` from the bundled `app/data/rdc-regions-footprints.json`.

#### `GET /api/v1/footprints/regions`

Lists all canonical regions with their covered states and SVG polygon paths (for frontend map rendering).

Response (`list[RegionResponse]`):

```json
[
  {
    "id": "southeast",
    "display_name": "Southeast",
    "svg_polygon_path": "M...",
    "svg_view_box": "0 0 1000 600",
    "label_x": 720.5,
    "label_y": 410.0,
    "states": ["AL", "FL", "GA", "MS", "SC", "TN"]
  }
]
```

#### `GET /api/v1/footprints/regions/resolve?alias=<text>`

Resolves either a canonical region ID or a known alias (case/whitespace-insensitive) to the canonical region. Returns `null` fields if unknown.

Example:

```bash
curl -sG https://api.usetorque.co/api/v1/footprints/regions/resolve \
  --data-urlencode 'alias=Gulf Coast'
```

Response (`RegionAliasResolutionResponse`):

```json
{
  "alias": "Gulf Coast",
  "canonical_region_id": "south",
  "canonical_region_name": "South"
}
```

#### `GET /api/v1/footprints/tickers`

Lists every ticker with its aggregate footprint summary — retail / fulfillment counts, average sqft, key markets, facility types, and the set of canonical regions covered.

Response (`list[TickerFootprintSummaryResponse]`):

```json
[
  {
    "symbol": "WMT",
    "company_name": "Walmart Inc.",
    "retail_location_count": 4616,
    "fulfillment_center_count": 210,
    "average_square_footage": 178000,
    "key_markets": ["Atlanta", "Dallas", "Houston"],
    "facility_types": ["distribution_center", "fulfillment_center", "store"],
    "regions": ["midwest", "northeast", "south", "southeast", "west"]
  }
]
```

#### `GET /api/v1/footprints/tickers/{ticker_symbol}/facilities`

Lists facilities for a ticker. Supports two optional query filters:

| Query param | Behavior |
|---|---|
| `region_id` | Filter by canonical region. Accepts either a canonical ID (`southeast`) or a known alias (`Gulf Coast`) — both are normalized server-side. |
| `state` | Filter by US state code (case-insensitive, e.g. `ga` or `GA`). |

Example:

```bash
curl -s 'https://api.usetorque.co/api/v1/footprints/tickers/WMT/facilities?state=GA'
```

Response (`list[FacilityResponse]`):

```json
[
  {
    "id": "7f0e8d...",
    "ticker_symbol": "WMT",
    "region_id": "southeast",
    "raw_region_value": "Southeast",
    "name": "Walmart DC 6094 - Douglas, GA",
    "facility_type": "distribution_center",
    "state": "GA",
    "country": "US",
    "latitude": null,
    "longitude": null,
    "geometry_status": "pending",
    "external_source_name": "rdc_sample_json",
    "external_facility_id": "WMT:walmart_dc_6094_douglas_ga:GA:distribution_center",
    "first_seen_at": "2026-04-20T13:45:01.000Z",
    "last_seen_at": "2026-04-20T13:45:01.000Z",
    "is_active": true
  }
]
```

---

### Analysis

Kicks off a simulated satellite-analysis pipeline on Celery. Real provider adapters (Earth Engine, VIIRS, Landsat, Sentinel, weather, trends) are **not wired yet** — the pipeline body is placeholder logic that walks the step state machine with fake scores so the whole async contract can be exercised end-to-end.

#### `POST /api/v1/analysis/runs`

Creates a new `AnalysisRun` and enqueues `run_analysis_pipeline` to Celery. Returns **202 Accepted** with the run record including a Celery `job_id`.

Request (`CreateAnalysisRunRequest`):

```json
{
  "ticker": "WMT",
  "time_range": "earnings_window"
}
```

Response (`AnalysisRunResponse`, status `202`):

```json
{
  "id": "c7e4...",
  "ticker": "WMT",
  "time_range": "earnings_window",
  "status": "queued",
  "progress": 0,
  "requested_by": "anonymous",
  "job_id": "a1b2...",
  "error_message": null,
  "created_at": "2026-04-20T14:00:00Z",
  "updated_at": "2026-04-20T14:00:00Z"
}
```

Authenticated requests (when `API_REQUIRE_AUTH=true`) have `requested_by` set to the auth subject; otherwise it falls back to `"anonymous"`.

#### `GET /api/v1/analysis/runs/{run_id}`

Returns the current run state. Poll this or (preferred) use the SSE stream below.

`status` transitions: `queued` → `running` → `completed` | `failed`. `progress` goes 0 → 100.

#### `GET /api/v1/analysis/runs/{run_id}/events`

Returns the ordered list of `AnalysisRunEvent` rows — one per pipeline step (`validate`, `footprint`, `weather`, `night_lights`, `optical`, `scores`, `finalize`, `completed`/`failed`).

#### `GET /api/v1/analysis/runs/{run_id}/report`

Returns the final `AnalysisReport` once the run is `completed`. 404 until then.

Response (`AnalysisReportResponse`):

```json
{
  "id": "...",
  "analysis_run_id": "...",
  "ticker": "WMT",
  "stance": "bullish",
  "confidence": 72,
  "consensus_score": 0.41,
  "narrative": "Simulated report for WMT...",
  "report_json": {
    "ticker": "WMT",
    "time_range": "earnings_window",
    "stance": "bullish",
    "confidence": 72,
    "consensus_score": 0.41,
    "module_outputs": [
      {"source": "weather", "directional_score": 0.12},
      {"source": "night_lights", "directional_score": 0.37},
      {"source": "optical", "directional_score": 0.22}
    ],
    "limitations": [
      "This is a local simulated pipeline.",
      "Real provider integrations are not wired yet."
    ]
  },
  "created_at": "..."
}
```

#### `GET /api/v1/analysis/runs/{run_id}/stream` (Server-Sent Events)

Streams events as the worker progresses. Content-Type: `text/event-stream`.

Each step event:
```
data: {"id":"...","step_key":"weather","status":"running","message":"Fetching weather context","payload":{...},"created_at":"..."}
```

On terminal state, a single `complete` event is emitted then the stream closes:
```
event: complete
data: {"run_id":"...","status":"completed","progress":100,"error_message":null}
```

Example:

```bash
curl -N https://api.usetorque.co/api/v1/analysis/runs/<RUN_ID>/stream
```

---

## Local development

```bash
cp .env.example .env
# Edit .env to set MINIO_ACCESS_KEY / MINIO_SECRET_KEY or flip AUTH_MOCK_MODE=true
docker compose up --build
```

Then:

- Swagger UI: <http://localhost:8000/docs>
- MinIO console: <http://localhost:9003> (login with the `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` you set)

Seed the sample footprint data once:

```bash
make seed-rdc
# or
docker compose exec api python -m scripts.seed_rdc
```

Run lint and tests:

```bash
./.venv/bin/ruff check .
./.venv/bin/pytest -q
```

---

## Production operations

### Deploying a change

1. Merge to `main`.
2. GitHub Actions (`docker-publish.yml`) builds & pushes:
   - `ghcr.io/shahzad-skoop/torque-backend:prod` (mutable)
   - `ghcr.io/shahzad-skoop/torque-backend:<short-sha>` (immutable)
3. Watchtower on the server pulls the new digest within ~60s and recreates `torque-backend-api` + `torque-backend-worker` in place.
4. `alembic upgrade head` runs on API container boot.

### Common ops commands (on the server)

```bash
# Watch logs
docker logs -f torque-backend-api
docker logs -f torque-backend-worker

# Health probes from the host
curl -s http://127.0.0.1:18080/api/v1/health
curl -s http://127.0.0.1:18080/api/v1/health/ready

# Seed / re-seed footprint data (idempotent)
docker exec torque-backend-api python -m scripts.seed_rdc

# Open a DB shell via the API container's network
docker exec -it torque-postgres psql -U torque -d torque_backend

# Run an ad-hoc migration
docker exec torque-backend-api alembic upgrade head
docker exec torque-backend-api alembic history --verbose

# Force-redeploy (bypass Watchtower wait)
docker compose -f /opt/apps/torque-backend/compose.yml pull
docker compose -f /opt/apps/torque-backend/compose.yml up -d
```

### Required production env (`.env` on the server)

See `.env.example` — at minimum these must be real secrets in prod:

- `DATABASE_URL`
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (app-scoped, **not** MinIO root)
- `AUTH_SERVICE_BASE_URL`, `AUTH_APP_SECRET`, `AUTH_CLIENT_SECRET`
- `SESSION_COOKIE_SECURE=true`
- `APP_ENV=production`
- `AUTH_MOCK_MODE=false`, `API_REQUIRE_AUTH=true`

The app **refuses to serve MinIO access** in production (`APP_ENV=production`) if `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` are empty — it raises `StorageConfigurationError` so you don't silently fall back to root credentials.

---

## CI / CD

| Workflow | File | Triggers | What it does |
|---|---|---|---|
| CI | `.github/workflows/ci.yml` | every push, every PR | Ruff + pytest against SQLite |
| Docker publish | `.github/workflows/docker-publish.yml` | push to `main`, `workflow_dispatch` | Builds image, pushes `prod` + short-SHA + `sha-<full>` tags to GHCR |

Uses only the built-in `GITHUB_TOKEN` — no external secrets needed.

---

## Implemented vs scaffolded

**Implemented**

- Health endpoints (liveness + readiness)
- Auth proxy (login / signup) with HttpOnly + Secure + SameSite cookie
- Analysis run lifecycle (create / poll / events / report / SSE stream)
- Celery task plumbing with a simulated analysis pipeline and a beat heartbeat
- Full RDC / footprint data model with seedable sample data
- Region alias normalization
- Production-safe MinIO configuration (app-scoped creds, prod-guarded)
- Dockerized local stack, GHCR CI/CD, server compose, Watchtower-based rollout

**Still scaffolded (intentional)**

- Real provider adapters (Earth Engine, VIIRS, Landsat, Sentinel, weather, trends)
- Real auth token verification / session strategy beyond the cookie plumbing
- MinIO artifact uploads for intermediate and final outputs
- Real report generation logic (replace `run_analysis_pipeline` body)
- Ticker / facility ingestion pipelines from external APIs
- Billing (Stripe)
- Role-based authorization beyond `get_current_subject`

The analysis pipeline stays simulated so the async contract (POST → 202 → worker → events → SSE → report) can be exercised end-to-end before real providers are wired in.

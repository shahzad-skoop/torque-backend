# Torque Backend

Production-minded FastAPI backend for the Torque intelligence platform.

This repository includes a locally runnable backend application with:

- FastAPI API server
- PostgreSQL + PostGIS
- Redis
- Celery worker + beat
- MinIO object storage
- Docker Compose for local testing
- Alembic migrations
- GitHub Actions CI
- External auth-service adapter with local mock mode

## Stack

- **API**: FastAPI
- **Queue**: Celery + Redis
- **DB**: PostgreSQL 16 + PostGIS
- **Storage**: MinIO
- **Migrations**: Alembic
- **Task runner**: Celery worker + Celery beat
- **Tests/Lint**: pytest + Ruff

## Implemented

- Health endpoints
- Auth proxy endpoints:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/signup`
- Analysis run lifecycle:
  - `POST /api/v1/analysis/runs`
  - `GET /api/v1/analysis/runs/{run_id}`
  - `GET /api/v1/analysis/runs/{run_id}/report`
  - `GET /api/v1/analysis/runs/{run_id}/events`
  - `GET /api/v1/analysis/runs/{run_id}/stream` (SSE)
- Simulated Celery analysis pipeline for local end-to-end testing
- RDC/footprint domain model with seedable sample data

## Still scaffolded (intentional)

- Real satellite provider integrations
- Real auth token verification flow with your auth service
- Real billing
- Real report generation logic
- Real MinIO artifact uploads
- Advanced role-based authorization

The analysis pipeline remains simulated so the full backend flow can be tested locally.

## Local development

### 1. Copy env

```bash
cp .env.example .env
```

### 2. Start everything

```bash
docker compose up --build
```

### 3. Open

- API docs: `http://localhost:8000/docs`
- MinIO console: `http://localhost:9001`

### 4. Run migrations manually (optional)

```bash
alembic upgrade head
```

The local API container already runs migrations on startup; this is mainly useful for manual local runs.

### Seed RDC sample data

```bash
make seed-rdc
# or:
python -m scripts.seed_rdc
```

The seed is idempotent and safe to re-run in local/dev.

---

## Default local credentials

### MinIO
- Access key: `minioadmin`
- Secret key: `minioadmin`

### Auth behavior
By default, `.env.example` uses:

```env
AUTH_MOCK_MODE=true
API_REQUIRE_AUTH=false
```

That lets you test locally without depending on the external auth service.

---

## API examples

### Mock login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@torque.local","password":"ABC123ab#c"}'
```

### Create analysis run

```bash
curl -X POST http://localhost:8000/api/v1/analysis/runs \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"WMT","time_range":"earnings_window"}'
```

### Poll run

```bash
curl http://localhost:8000/api/v1/analysis/runs/<RUN_ID>
```

### Stream run via SSE

```bash
curl http://localhost:8000/api/v1/analysis/runs/<RUN_ID>/stream
```

---

## Suggested next implementation steps

1. Replace simulated Celery analysis with real provider adapters:
   - Google Earth Engine
   - VIIRS
   - Landsat
   - Sentinel-1 / Sentinel-2
   - Weather
   - Trends
2. Add real auth token validation / session strategy
3. Add MinIO artifact uploads for intermediate and final outputs
4. Add ticker/facility ingestion pipelines
5. Add report exports
6. Add Stripe later

---

## RDC footprint schema overview

The backend now includes normalized tables for region + facility footprint modeling:

- `regions`: canonical region metadata including display name and SVG polygon path.
- `region_aliases`: alias normalization map (e.g. "southeast" -> "south").
- `region_states`: region to US state mapping.
- `tickers` (extended): ticker/company plus retail/facility summary metrics.
- `ticker_regions`: canonical region coverage per ticker.
- `ticker_key_markets`: key market cities per ticker.
- `ticker_facility_types`: supported facility/operational types per ticker.
- `facilities` (extended): physical facilities with both raw region and canonical `region_id`, plus ingestion metadata fields (`external_source_name`, `external_facility_id`, payload, first/last seen, active status) and staged geometry fields (`latitude`, `longitude`, `geometry_wkt`, `polygon_geojson`, `geometry_status`, `polygon_source`).

### Geometry strategy

This schema keeps geometry fields in JSON/text/lat-lng for immediate compatibility while preserving a clean migration path to full PostGIS geometry columns later. No production data model rewrite is required when richer geometry ingestion is turned on.

### Verification endpoints

- `GET /api/v1/footprints/regions`
- `GET /api/v1/footprints/regions/resolve?alias=Southeast`
- `GET /api/v1/footprints/tickers`
- `GET /api/v1/footprints/tickers/{symbol}/facilities`

### Local verification flow

```bash
docker compose up --build
# in another shell:
python -m scripts.seed_rdc
curl http://localhost:8000/api/v1/footprints/tickers
curl "http://localhost:8000/api/v1/footprints/regions/resolve?alias=Gulf%20Coast"
curl "http://localhost:8000/api/v1/footprints/tickers/WMT/facilities?state=GA"
```

## Out of scope in this repo stage

- Production host/server deployment setup
- Watchtower/GHCR/runtime orchestration changes
- Cloudflare/routing/infrastructure automation

---

## CI

GitHub Actions runs:

- Ruff
- Pytest

The current tests use SQLite locally in CI, so CI does not need Postgres or Redis to run.

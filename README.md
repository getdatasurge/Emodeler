# EnergyModeler

An open-methodology web platform for **window-film energy savings analysis** — a
modern, dealer-owned replacement for 3M EFILM. Same engine (EnergyPlus), same
authoritative public data sources (LBNL IGSDB, NREL NSRDB/PVWatts, OpenEI URDB,
EPA eGRID, DOE Commercial Prototype Buildings), with cloud access, multi-film
comparison, branded reports, and an auditable run bundle.

> **Status: rough beta (v0.1.0-beta).** The full system is wired end to end:
> project intake → glazing/faces → film selection → calculation → results
> dashboard → branded report + auditable bundle. See the methodology caveat
> below regarding the calculation engine.

---

## Methodology & the engine caveat (read this first)

The production calculation engine is **EnergyPlus** — the platform builds real
IDF files, submits them to the EnergyPlus 24.x binary, and parses the output.
Per the spec (and 3M's own guidance), a single-SHGC analytical shortcut is
**never** an acceptable methodology for a customer-facing bid.

This beta ships an **analytical fallback engine** that runs when the EnergyPlus
binary is not configured (local dev, CI, demos). Every result it produces is
stamped `engine_mode: "analytical_estimate"` and carries a prominent warning. It
is **not valid for bids, utility rebate filings, or LEED.** To get audited
results, provide EnergyPlus (`ENERGYPLUS_DIR`) and the DOE prototype IDFs — the
real pipeline (`engine/runner.py` → IDF build → subprocess → parse) then runs
automatically. `GET /api/meta` reports which engine is active.

All upstream integrations (NREL, OpenEI, IGSDB) similarly run live when an API
key is set and fall back to bundled offline data otherwise, so the beta runs
with zero external dependencies.

---

## Quickstart

### Backend (FastAPI)
```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- API docs (OpenAPI/Swagger): http://localhost:8000/docs
- Health: http://localhost:8000/api/health · Engine status: http://localhost:8000/api/meta
- A demo project (Zephyrhills FL — FX-01) is seeded on first run.

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api → :8000)
```

### Docker (backend + frontend)
```bash
docker compose up --build          # api :8000, frontend :5173
docker compose --profile full up   # + Redis + EnergyPlus Celery worker
```

### Tests
```bash
cd backend && . .venv/bin/activate && python -m pytest -q
```

---

## Architecture

```
Browser (React/TS, Vite, Tailwind)
        │  HTTPS  /api/*
        ▼
FastAPI gateway ── SQLite (beta) / Postgres+Supabase (prod)
        │              ▲
        │  enqueue     │ persist results + audit bundle
        ▼              │
Calc pipeline ──► EnergyPlus worker (Celery, prod)  ──►  Object store (R2/S3, prod)
                 └── analytical estimate (beta fallback)
```

Engine pipeline (spec Ch 5–6): load DOE prototype → scale to floor area → bind
TMY3 weather → swap glazing construction per scenario (baseline + N films) → run
→ parse end-uses/peak/window gains → economics (payback/NPV/IRR) + carbon
(eGRID) → comparison → branded report + audit bundle (IDFs, results, methodology).

### Repository layout
```
backend/
  energy_modeler/            # calc engine package
    economics.py carbon.py leed.py schemas.py datastore.py config.py
    engine/                  # idf_builder, glazing, film_catalog, igsdb_client,
                             # weather, prototype_loader, outputs, runner, estimate
    parser/                  # eplus_html, results
    data/                    # films(16 3M SKUs), base_glazings, egrid_2023,
                             # zip_crosswalk, prototypes, climate_solar
  app/                       # FastAPI: main, db, models, routers/, pipeline, report
  workers/eplus_worker.py    # Celery worker (prod async path)
  db/schema.sql              # canonical Postgres DDL
  tests/                     # pytest (engine, economics, carbon, leed, API e2e)
frontend/                    # React + TS + Vite + Tailwind
docker-compose.yml  .github/workflows/ci.yml  docs/
```

## Key API endpoints (spec Ch 10)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/meta` | Engine + integration status (drives the estimate banner) |
| GET | `/api/solar/{zip}` `/api/utility/{zip}` `/api/climate-zone/{zip}` `/api/egrid/{zip}` | Intake auto-fill |
| GET | `/api/films` · `/api/films/{sku}` · `/api/films/{sku}/pairings/{base}` | Catalog |
| POST/GET/PATCH | `/api/projects` · `/api/projects/{id}` | Projects |
| POST | `/api/calc/run` | Dispatch baseline + N candidate films → `job_id` |
| GET | `/api/jobs/{id}` · `/api/jobs/{id}/audit-bundle` | Poll + audit download |
| GET/POST | `/api/reports/{job_id}` | Branded report (HTML; WeasyPrint PDF in prod) |

## Data sources (all free / public)
LBNL IGSDB (glazing optics) · NREL NSRDB & PVWatts v8 (weather/solar) · OpenEI
URDB (utility rates) · EPA eGRID 2023 (carbon) · DOE Commercial Prototype
Buildings (geometry) · ASHRAE 90.1 / NFRC 100/200 / ISO 15099 (standards).

## Roadmap (spec Ch 11.4)
- **Phase 1 (this beta → MVP):** EnergyPlus pipeline, 16 3M SKUs, 8 prototypes, branded PDF, validation on 5 reference projects.
- **Phase 2:** full ~30-SKU catalog, WinTracker LiDAR import, live OpenEI auto-fill, demand-charge preview, recommended-film engine.
- **Phase 3:** ASHRAE 90.1 Appendix G baseline + PCI/PCIt + LEED v4.1 EAc estimator, hourly demand-charge modeling, PE-stamp methodology appendix.
- **Phase 4:** multi-tenant SaaS, non-3M catalogs, residential prototypes.

## License / ownership
The wrapper (web app, workflow, branded outputs) is the proprietary component
owned by Sustainable Finishes. Every external data source is free and public.

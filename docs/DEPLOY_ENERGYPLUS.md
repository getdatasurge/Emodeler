# Deploying the bid-grade EnergyPlus engine

The default deploy (Render/Pages) runs the **analytical estimate** — fine for
previews, explicitly *not* for bids. ESCO / performance-contract work needs the
real engine: EnergyPlus 22.1 simulating the DOE prototypes against TMY3 weather.
This is the worker stack.

```
API (FastAPI)  --enqueue (Redis)-->  EnergyPlus worker (Celery)
   builds the job                     loads prototype IDF -> applies film +
   returns job_id                     COP + outputs -> runs EnergyPlus -> parses
```

## 1. Pick a host
EnergyPlus needs the real binary, ~1–2 GB RAM, and minutes of CPU per scenario —
free/ephemeral tiers won't run it. Simplest to validate: **one small VM** (Hetzner
~€4/mo, DigitalOcean $6/mo, or a Fly.io machine) with Docker. For production
multi-tenant SaaS, move the worker to a managed service (Render paid Background
Worker + Key Value Redis, or Fly).

## 2. Bring up the stack
```bash
git clone <repo> && cd Emodeler
export NREL_API_KEY=...        # free, instant: developer.nrel.gov/signup (live solar + utility)
export IGSDB_API_TOKEN=...     # optional: live glazing optics
docker compose --profile full up --build -d   # api + redis + EnergyPlus worker
```
Set `REDIS_URL` on the **api** service (compose passes `redis://redis:6379/0`) so
the API enqueues jobs to the worker instead of running them inline. With the
worker up + `ENERGYPLUS_DIR` resolving the binary, `GET /api/meta` flips to
`"engine_mode":"energyplus"`.

## 3. Populate prototypes + weather (one time, into the shared volume)
```bash
# DOE Commercial Prototype IDFs (~50 MB) -> /opt/energyplus/prototypes
docker compose exec worker python scripts/fetch_prototypes.py --write-manifest
# TMY3 .epw per station -> <STORAGE_DIR>/weather  (set WEATHER_BASE_URL to your EPW host)
docker compose exec worker python scripts/fetch_weather.py --all
```
`engine/prototype_loader.py` and `engine/weather.py::epw_for_zip` read from these;
until they're present the engine raises `PrototypeNotFound`/`FileNotFoundError`
and the runner cleanly falls back to the labeled estimate.

## 4. Verify it's real
- `GET /api/meta` → `energyplus_available: true`, `engine_mode: "energyplus"`.
- Run an analysis; the result's `engine_mode` is `"energyplus"` and the warning
  banner disappears. The audit bundle now contains the real `eplusout.eso` /
  `eplustbl.csv` + the proposed IDFs — third-party reproducible (spec Ch 2.5).

## 5. Validate before quoting (spec Ch 12)
```bash
docker compose exec worker python -m pytest -m eplus -q   # the 5 reference fixtures
```
FX-01…FX-05 must land in the published ranges (§12.1); run the EFILM cross-check
(`docs/EFILM_CROSSCHECK.md`). **A PE should review the methodology before the
numbers back a guaranteed-savings contract (§8.4).**

## Notes
- The `energyplus` binary and `Energy+.idd` are auto-detected from PATH (the nrel
  image installs them under a hash-suffixed dir), so the Dockerfiles don't pin
  `ENERGYPLUS_DIR`. Set it explicitly only for a non-standard install. Verify with
  `docker compose exec worker energyplus --version`.
- The binary is pinned to **22.1.0** to match the bundled DOE prototype IDFs;
  running them on a newer binary fails (shifted object fields). Bump both together.
- Scale throughput by adding worker replicas (one EnergyPlus run per worker;
  `--concurrency=1`).
- Persist the shared volume (prototypes, weather, SQLite/Postgres, audit bundles).

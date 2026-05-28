# Deploying EnergyModeler

GitHub Pages hosts the **frontend** (static). To make it functional you deploy
the **FastAPI backend** to a host and point the Pages site at it. The backend
already sends permissive CORS (`*`), so a cross-origin call from
`https://getdatasurge.github.io` works out of the box.

```
GitHub Pages (frontend)  ──HTTPS /api/*──►  Backend host (FastAPI, Docker)
   set VITE_API_BASE                         backend/Dockerfile, binds $PORT
```

> Engine note: the API image (`backend/Dockerfile`) runs the **analytical
> estimate** engine (no EnergyPlus binary). That's the current beta behavior and
> is fine for a working demo. Real EnergyPlus runs use the heavier worker image
> (`backend/Dockerfile.worker`) + DOE prototype IDFs — see spec Ch 9.5.

---

## 1. Deploy the backend

### Option A — Render (easiest, free tier)
1. Push this repo to GitHub (done).
2. Render dashboard → **New + → Blueprint** → select this repo. Render reads
   [`render.yaml`](../render.yaml) and creates the `energymodeler-api` web service
   from `backend/Dockerfile`.
3. Deploy. When live, note the URL, e.g. `https://energymodeler-api.onrender.com`.
4. Verify: open `https://<your-url>/api/health` → `{"status":"ok",...}`.

*Free plan caveats:* the service cold-starts after inactivity (~30–60 s first
request) and has no persistent disk, so the SQLite DB + audit bundles reset on
restart (the demo project re-seeds automatically). Add a Render Disk mounted at
`/data` for persistence.

### Option B — Fly.io
```bash
cd backend
fly launch --copy-config --no-deploy   # uses backend/fly.toml; pick a unique app name
fly deploy
fly open                                # prints https://<app>.fly.dev
```
Building from `backend/` keeps the Docker context aligned with the Dockerfile.
Add a volume for persistence (commented block in `backend/fly.toml`).

### Option C — Railway / others
Any host that builds a Dockerfile works: point it at `backend/` with
`backend/Dockerfile`. The container listens on `$PORT` (falls back to 8000).

---

## 2. Point the Pages site at the backend
1. Repo → **Settings → Secrets and variables → Actions → Variables → New
   repository variable**: name `VITE_API_BASE`, value your backend URL (e.g.
   `https://energymodeler-api.onrender.com`, no trailing slash).
2. **Actions → "Deploy frontend to GitHub Pages" → Run workflow** (branch
   `main`). The build injects `VITE_API_BASE`, so the published site now calls
   your backend.
3. Open `https://getdatasurge.github.io/Emodeler/` — the "backend not reachable"
   notice is gone, the demo project loads, and you can run an analysis end to end.

## 3. (Optional) Live external data
Set `NREL_API_KEY` (PVWatts + OpenEI) and `IGSDB_API_TOKEN` on the backend host
to replace the bundled offline data with live lookups. Without them the platform
uses bundled climate/eGRID/film data — fully functional, just not live.

## Troubleshooting
- **Pages still shows "backend not reachable":** confirm the `VITE_API_BASE`
  variable is set and you re-ran the Pages workflow *after* setting it (the URL
  is baked in at build time).
- **CORS error in the browser console:** the backend allows `*`; make sure
  `VITE_API_BASE` has no trailing slash and uses `https://`.
- **404 from the backend URL:** check the host's logs and that `/api/health`
  responds; free hosts may still be cold-starting.

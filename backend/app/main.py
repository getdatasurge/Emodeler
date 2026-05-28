"""FastAPI application entrypoint (spec Ch 9/10)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from energy_modeler import __version__
from energy_modeler.config import settings

from .auth import require_auth
from .db import init_db
from .errors import install_error_handling
from .routers import calc, films, jobs, lookups, projects, reports
from .seed import seed_demo


def _init_sentry() -> None:
    """No-op unless SENTRY_DSN is set (and sentry-sdk is installed)."""
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        return
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, send_default_pii=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_demo()
    yield


_init_sentry()

app = FastAPI(
    title="EnergyModeler API",
    version=__version__,
    description="Open-methodology window-film energy savings platform (EnergyPlus wrapper).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # single-tenant beta; tighten per deployment
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handling(app)

# require_auth is permissive until AUTH_ENFORCED=true (spec Ch 1.1); health/meta
# and the docs stay open.
for r in (lookups, films, projects, calc, jobs, reports):
    app.include_router(r.router, dependencies=[Depends(require_auth)])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


@app.get("/api/meta")
def meta():
    """Engine + data status — drives the 'estimate vs EnergyPlus' UI banner."""
    energyplus = settings.energyplus_exe
    return {
        "version": __version__,
        "engine_mode": "energyplus" if energyplus else "analytical_estimate",
        "energyplus_available": bool(energyplus),
        "nrel_live": bool(settings.nrel_api_key),
        "igsdb_live": bool(settings.igsdb_api_token),
        "notice": (
            None if energyplus else
            "EnergyPlus binary not configured — results are labeled analytical "
            "estimates, not valid for bids. Set ENERGYPLUS_DIR for audited runs."
        ),
    }


@app.get("/")
def root():
    return {"name": "EnergyModeler API", "version": __version__, "docs": "/docs"}

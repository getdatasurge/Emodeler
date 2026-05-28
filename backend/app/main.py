"""FastAPI application entrypoint (spec Ch 9/10)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from energy_modeler import __version__
from energy_modeler.config import settings

from .db import init_db
from .routers import calc, films, jobs, lookups, projects, reports
from .seed import seed_demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_demo()
    yield


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

for r in (lookups, films, projects, calc, jobs, reports):
    app.include_router(r.router)


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

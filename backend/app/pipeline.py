"""Calculation pipeline + audit bundle (spec Ch 9.4, 2.5).

Maps a persisted Project onto an EngineProject, runs the engine, persists the
ProjectComparison, and assembles the auditable bundle (IDFs, parsed results,
methodology statement) that a third party can re-run."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone

from energy_modeler import __version__
from energy_modeler.config import settings
from energy_modeler.engine import idf_builder, runner
from energy_modeler.engine.inputs import (
    BUILDING_FIELDS,
    EngineFace,
    EngineOptions,
    EngineProject,
    EngineScenario,
)
from energy_modeler.parser import results

from .db import SessionLocal
from .models import CalculationJob, Project


def to_engine_project(project: Project, options: EngineOptions) -> EngineProject:
    return EngineProject(
        project_id=project.id,
        building_type=project.building_type,
        climate_zone=project.climate_zone,
        gross_floor_area_sf=project.gross_floor_area_sf,
        zip=project.zip,
        utility_rate_usd_kwh=project.utility_rate_usd_kwh,
        egrid_subregion=project.egrid_subregion,
        faces=[
            EngineFace(orientation=f.orientation, area_sqft=f.area_sqft, base_glazing_id=f.base_glazing_id)
            for f in project.faces
        ],
        scenarios=[
            EngineScenario(label=s.label, film_sku=s.film_sku, installed_cost_usd=s.installed_cost_usd)
            for s in project.scenarios
        ],
        options=options,
        **{k: getattr(project, k) for k in BUILDING_FIELDS},
    )


def _methodology_statement(comparison) -> str:
    energyplus = comparison.engine_mode == "energyplus"
    engine_line = (
        f"EnergyPlus {comparison.baseline.energyplus_version}"
        if energyplus
        else "ANALYTICAL ESTIMATE (EnergyPlus binary unavailable) — NOT for bid use"
    )
    return (
        f"EnergyModeler methodology statement\n"
        f"===================================\n"
        f"Platform version : {__version__}\n"
        f"Engine           : {engine_line}\n"
        f"Weather          : {comparison.baseline.weather_station} / "
        f"{comparison.baseline.weather_dataset}\n"
        f"Glazing optics   : LBNL IGSDB (3M monolithic glass+film records)\n"
        f"Carbon factors   : EPA eGRID 2023 subregion total output rates\n"
        f"Standards         : ASHRAE 90.1 prototypes; ISO 15099 convection; NFRC 100/200\n\n"
        f"The customer-facing savings reproduce from the bundled scenario IDFs run\n"
        f"against the referenced TMY3 weather file. See the EnergyPlus 24.x\n"
        f"Engineering Reference, Window Calculation Module, for the heat balance.\n"
    )


def build_audit_bundle(job_id: str, engine_project: EngineProject, comparison) -> str:
    """Write IDFs + parsed results + methodology to a folder and zip it."""
    base = settings.storage_dir / job_id
    bundle_dir = base / "audit"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    idf_builder.build_idfs(engine_project, bundle_dir / "idf")
    (bundle_dir / "results.json").write_text(
        json.dumps(comparison.model_dump(mode="json"), indent=2)
    )
    (bundle_dir / "METHODOLOGY.txt").write_text(_methodology_statement(comparison))

    archive = shutil.make_archive(str(base / f"audit_bundle_{job_id}"), "zip", bundle_dir)
    return archive


def run_job(job_id: str) -> None:
    """Background entrypoint: run the engine for a queued job and persist results.

    Opens its own session (runs after the HTTP response is sent)."""
    session = SessionLocal()
    try:
        job = session.get(CalculationJob, job_id)
        if job is None:
            return
        project = session.get(Project, job.project_id)
        if project is None:
            job.status = "failed"
            job.error_message = "Project not found"
            session.commit()
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.commit()

        raw_opts = job.options or {}
        opts = EngineOptions(
            film_life_yrs=raw_opts.get("film_life_yrs", 15),
            discount_rate=raw_opts.get("discount_rate", 0.05),
            utility_escalation=raw_opts.get("utility_escalation", 0.025),
            include_appendix_g_baseline=raw_opts.get("include_appendix_g_baseline", False),
        )
        engine_project = to_engine_project(project, opts)

        try:
            mode, baseline, film_runs = runner.run_project(engine_project)
            comparison = results.build_comparison(engine_project, baseline, film_runs, mode)
            bundle_path = build_audit_bundle(job_id, engine_project, comparison)

            job.engine_mode = mode
            job.energyplus_version = baseline.energyplus_version
            job.weather_station = baseline.weather_station
            job.scenarios_completed = len(film_runs)
            comparison.audit_bundle_path = bundle_path
            job.comparison = comparison.model_dump(mode="json")
            job.audit_bundle_path = bundle_path
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            project.status = "completed"
            session.commit()
        except Exception as exc:  # noqa: BLE001 - record failure for the poll endpoint
            session.rollback()
            job = session.get(CalculationJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.error_phase = "engine_run"
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
    finally:
        session.close()

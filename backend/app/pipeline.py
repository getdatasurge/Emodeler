"""Calculation pipeline + audit bundle (spec Ch 9.4, 2.5).

Maps a persisted Project onto an EngineProject, runs the engine, persists the
ProjectComparison, and assembles the auditable bundle (IDFs, parsed results,
methodology statement) that a third party can re-run."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

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
        gas_rate_usd_therm=project.gas_rate_usd_therm,
        egrid_subregion=project.egrid_subregion,
        faces=[
            EngineFace(
                orientation=f.orientation, area_sqft=f.area_sqft,
                base_glazing_id=f.base_glazing_id, tilt_deg=f.tilt_deg,
            )
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
        f"against the referenced TMY3 weather file. See the EnergyPlus 22.1\n"
        f"Engineering Reference, Window Calculation Module, for the heat balance.\n"
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _citations_text(engine_project: EngineProject, comparison) -> str:
    """Per-run citation block listing every upstream standard the result
    relies on, with the exact version / source identifier used. Anything a
    PE reviewer would want pointed at."""
    eplus_version = comparison.baseline.energyplus_version
    weather = comparison.baseline.weather_station
    weather_set = comparison.baseline.weather_dataset
    return (
        "# Bid-grade citations for this run\n\n"
        "## Engine\n"
        f"- EnergyPlus {eplus_version} (NREL/DOE, unmodified binary)\n"
        "- ASHRAE 140 validation inherited via the unmodified binary\n"
        f"- engine_mode: {comparison.engine_mode}\n\n"
        "## Prototype\n"
        "- DOE Commercial Prototype Buildings (PNNL, energycodes.gov)\n"
        "- Standard edition: ASHRAE 90.1-2019\n"
        f"- Building type: {engine_project.building_type}\n"
        f"- Climate zone: {engine_project.climate_zone}\n"
        f"- Nominal floor area: per prototype; project scaled to "
        f"{engine_project.gross_floor_area_sf:.0f} sf via parser_bridge._scale_run "
        f"(basis={engine_project.options.scaling_basis})\n\n"
        "## Weather\n"
        f"- Representative station: {weather}\n"
        f"- Dataset: {weather_set} (energycodes.gov IECC bundle)\n\n"
        "## Glazing optics\n"
        "- LBNL IGSDB (3M monolithic glass+film records)\n"
        "- Procedure: NFRC 200 (spectral or summary tier per record)\n"
        "- 3M angular optics rule (spec §2.1): films are NEVER characterized by\n"
        "  a single SHGC. EnergyPlus solves T(θ), R(θ), A(θ) per timestep.\n\n"
        "## Carbon factors\n"
        "- EPA eGRID 2023, subregion total output emissions rates\n"
        f"- Subregion: {engine_project.egrid_subregion}\n\n"
        "## Heat-balance method\n"
        "- ISO 15099 §8.3.2.2 interior convection\n"
        "- EnergyPlus Engineering Reference, Window Calculation Module\n\n"
        "## Economics\n"
        f"- Utility electric rate: ${engine_project.utility_rate_usd_kwh:.4f}/kWh\n"
        + (
            f"- Utility gas rate: ${engine_project.gas_rate_usd_therm:.3f}/therm\n"
            if engine_project.gas_rate_usd_therm is not None
            else "- Utility gas rate: NOT SET — heating-gas savings priced at $0\n"
        )
        + f"- Film life: {engine_project.options.film_life_yrs} yr; "
        f"discount {engine_project.options.discount_rate:.1%}; "
        f"utility escalation {engine_project.options.utility_escalation:.1%}\n"
        + (
            "\n## LEED PCI anchor (ASHRAE 90.1-2019 Appendix G)\n"
            f"- Same prototype + weather rerun with prescriptive fenestration "
            f"U={comparison.appendix_g.window_u_factor:.2f} BTU/h.ft^2.F, "
            f"SHGC={comparison.appendix_g.window_shgc} (Table G3.4).\n"
            f"- Project % total-electricity savings vs the Appendix G run: "
            f"{comparison.appendix_g.pct_savings_vs_code_baseline}%\n"
            f"- Project % cooling-electricity savings vs the Appendix G run: "
            f"{comparison.appendix_g.cooling_pct_savings_vs_code_baseline}%\n"
            if comparison.appendix_g is not None
            else ""
        )
    )


def _write_manifest(bundle_dir: Path) -> Path:
    """Compute SHA256 over every file in the bundle and write MANIFEST.sha256.

    sha256sum -c -compatible: `<hash>  <relative-path>` lines, sorted by path.
    A reviewer can verify any bundled artifact independently."""
    manifest_path = bundle_dir / "MANIFEST.sha256"
    lines: list[str] = []
    for path in sorted(bundle_dir.rglob("*")):
        if not path.is_file() or path.name == manifest_path.name:
            continue
        rel = path.relative_to(bundle_dir).as_posix()
        lines.append(f"{_sha256(path)}  {rel}")
    manifest_path.write_text("\n".join(lines) + "\n")
    return manifest_path


def build_audit_bundle(job_id: str, engine_project: EngineProject, comparison) -> str:
    """Write IDFs + parsed results + methodology + citations + manifest to a
    folder and zip it. MANIFEST.sha256 lets a reviewer verify every artifact
    independently; CITATIONS.md names every upstream standard with its exact
    source so the run is reproducible from primary data."""
    base = settings.storage_dir / job_id
    bundle_dir = base / "audit"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    idf_builder.build_idfs(engine_project, bundle_dir / "idf")
    (bundle_dir / "results.json").write_text(
        json.dumps(comparison.model_dump(mode="json"), indent=2)
    )
    (bundle_dir / "METHODOLOGY.txt").write_text(_methodology_statement(comparison))
    (bundle_dir / "CITATIONS.md").write_text(_citations_text(engine_project, comparison))
    _write_manifest(bundle_dir)

    archive = shutil.make_archive(str(base / f"audit_bundle_{job_id}"), "zip", bundle_dir)
    try:  # best-effort R2 upload; the local file remains the fallback
        from energy_modeler.objectstore import object_store

        object_store.upload_file(Path(archive), object_store.audit_key(job_id))
    except Exception:  # noqa: BLE001
        pass
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
            include_demand_charge=raw_opts.get("include_demand_charge", False),
            demand_charge_usd_per_kw=raw_opts.get("demand_charge_usd_per_kw", 0.0),
            scaling_basis=raw_opts.get("scaling_basis", "floor"),
        )
        engine_project = to_engine_project(project, opts)

        try:
            mode, baseline, film_runs, appendix_g_run = runner.run_project(engine_project)
            comparison = results.build_comparison(
                engine_project, baseline, film_runs, mode,
                appendix_g_run=appendix_g_run,
            )
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

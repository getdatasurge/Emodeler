"""Idempotent demo seed — creates the FX-01 Zephyrhills reference project so a
fresh install has something to run immediately."""
from __future__ import annotations

from .db import SessionLocal
from .models import CalculationJob, Face, Project, Scenario


def seed_demo() -> None:
    session = SessionLocal()
    job_id: str | None = None
    try:
        if session.query(Project).count() > 0:
            return
        project = Project(
            name="Zephyrhills FL — Reference (FX-01)",
            customer_name="Sample Commercial Office",
            city="Zephyrhills", state="FL", zip="33540",
            latitude=28.234, longitude=-82.176,
            climate_zone="2A", building_type="MediumOffice",
            gross_floor_area_sf=14500,
            utility_label="Tampa Electric Company — GS-1",
            utility_rate_usd_kwh=0.1145, utility_rate_source="urdb_default",
            egrid_subregion="FRCC", status="draft",
        )
        for orient, area in [("S", 873), ("E", 873), ("W", 874), ("N", 874)]:
            project.faces.append(
                Face(orientation=orient, area_sqft=area, base_glazing_id="dbl_clear_3mm_13mmAir")
            )
        for label, sku, cost in [
            ("Good", "3M-PR40X", 43675.0),
            ("Better", "3M-NV35", 38420.0),
            ("Best", "3M-PR70X", 52890.0),
        ]:
            project.scenarios.append(Scenario(label=label, film_sku=sku, installed_cost_usd=cost))
        session.add(project)
        session.commit()

        # Pre-run the analysis so a fresh deploy shows a full results dashboard
        # immediately (the analytical estimate is sub-second; no manual run).
        job = CalculationJob(
            project_id=project.id,
            status="queued",
            scenarios_total=len(project.scenarios),
            options={
                "film_life_yrs": 15,
                "discount_rate": 0.05,
                "utility_escalation": 0.025,
                "include_appendix_g_baseline": False,
            },
        )
        session.add(job)
        project.status = "in_analysis"
        session.commit()
        job_id = job.id
    finally:
        session.close()

    if job_id is not None:
        # Runs in its own session; sets the project to 'completed' on success.
        from .pipeline import run_job

        try:
            run_job(job_id)
        except Exception:  # noqa: BLE001 - demo seeding must never block startup
            pass

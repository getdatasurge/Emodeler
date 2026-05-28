"""Calculation dispatch (spec Ch 10.2). POST /api/calc/run enqueues baseline +
N candidate scenarios and returns a job id; the browser polls /api/jobs/{id}."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from energy_modeler import datastore

from .. import pipeline
from ..db import get_session
from ..models import CalculationJob, Project, Scenario
from ..schemas_api import CalcRunRequest

router = APIRouter(tags=["calc"])

RUNTIME_HINT_SEC = {
    "SmallOffice": 45, "MediumOffice": 120, "LargeOffice": 600,
    "PrimarySchool": 180, "SecondarySchool": 360,
}


@router.post("/api/calc/run", status_code=202)
def run_calc(
    body: CalcRunRequest,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
):
    project = session.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": body.project_id}})
    if not project.faces:
        raise HTTPException(status_code=422, detail={
            "error": "Project has no glazing faces", "code": "VALIDATION_FAILED",
            "details": {"project_id": body.project_id}})

    # Optional inline scenario override replaces the project's stored scenarios.
    if body.scenarios:
        session.query(Scenario).filter(Scenario.project_id == project.id).delete()
        for s in body.scenarios:
            if datastore.get_film(s.film_sku) is None:
                raise HTTPException(status_code=422, detail={
                    "error": f"Unknown film SKU {s.film_sku}", "code": "VALIDATION_FAILED",
                    "details": {"film_sku": s.film_sku}})
            session.add(Scenario(project_id=project.id, label=s.label, film_sku=s.film_sku,
                                 installed_cost_usd=s.installed_cost_usd))
        session.commit()
        session.refresh(project)

    if not project.scenarios:
        raise HTTPException(status_code=422, detail={
            "error": "No candidate film scenarios", "code": "VALIDATION_FAILED",
            "details": {"project_id": body.project_id}})

    job = CalculationJob(
        project_id=project.id,
        status="queued",
        scenarios_total=len(project.scenarios),
        options=body.options.model_dump(),
    )
    session.add(job)
    project.status = "in_analysis"
    session.commit()

    background.add_task(pipeline.run_job, job.id)

    return {
        "job_id": job.id,
        "status": "queued",
        "estimated_runtime_sec": RUNTIME_HINT_SEC.get(project.building_type, 120),
        "poll_url": f"/api/jobs/{job.id}",
    }

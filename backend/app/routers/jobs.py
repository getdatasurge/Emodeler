"""Job polling + audit bundle download (spec Ch 10.3, 2.5)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import CalculationJob

router = APIRouter(tags=["jobs"])


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(CalculationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "Job not found",
                            "code": "NOT_FOUND", "details": {"job_id": job_id}})

    if job.status == "running":
        return {"job_id": job.id, "status": "running",
                "progress": {"scenarios_completed": job.scenarios_completed,
                             "scenarios_total": job.scenarios_total}}
    if job.status == "failed":
        return {"job_id": job.id, "status": "failed",
                "error_message": job.error_message, "error_phase": job.error_phase}
    if job.status == "completed":
        comparison = job.comparison or {}
        films = comparison.get("films", [])
        return {
            "job_id": job.id,
            "status": "completed",
            "engine_mode": job.engine_mode,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "results_url": f"/api/projects/{job.project_id}/results",
            "audit_bundle_url": f"/api/jobs/{job.id}/audit-bundle",
            "warnings": comparison.get("warnings", []),
            "baseline": comparison.get("baseline"),
            "scenario_results": films,
        }
    return {"job_id": job.id, "status": job.status}


@router.get("/api/jobs/{job_id}/results")
def get_job_full(job_id: str, session: Session = Depends(get_session)):
    job = session.get(CalculationJob, job_id)
    if job is None or job.status != "completed":
        raise HTTPException(status_code=404, detail={"error": "No completed results",
                            "code": "NOT_FOUND", "details": {"job_id": job_id}})
    return job.comparison


@router.get("/api/jobs/{job_id}/audit-bundle")
def get_audit_bundle(job_id: str, session: Session = Depends(get_session)):
    job = session.get(CalculationJob, job_id)
    if job is None or not job.audit_bundle_path:
        raise HTTPException(status_code=404, detail={"error": "No audit bundle",
                            "code": "NOT_FOUND", "details": {"job_id": job_id}})
    path = Path(job.audit_bundle_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail={"error": "Audit bundle file missing",
                            "code": "NOT_FOUND", "details": {"job_id": job_id}})
    return FileResponse(path, media_type="application/zip", filename=path.name)

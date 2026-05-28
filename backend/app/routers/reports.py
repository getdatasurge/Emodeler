"""Report generation (spec Ch 10.5). Beta returns branded HTML (printable to
PDF); production swaps in WeasyPrint server-side rendering."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import CalculationJob, Project
from ..report import render_report_html
from ..routers.projects import _serialize

router = APIRouter(tags=["reports"])


def _load(job_id: str, session: Session):
    job = session.get(CalculationJob, job_id)
    if job is None or job.status != "completed" or not job.comparison:
        raise HTTPException(status_code=404, detail={"error": "No completed analysis for report",
                            "code": "NOT_FOUND", "details": {"job_id": job_id}})
    project = session.get(Project, job.project_id)
    return job, project


@router.get("/api/reports/{job_id}", response_class=HTMLResponse)
def get_report(job_id: str, session: Session = Depends(get_session)):
    job, project = _load(job_id, session)
    return HTMLResponse(render_report_html(_serialize(project), job.comparison))


@router.post("/api/reports/{job_id}")
def generate_report(job_id: str, session: Session = Depends(get_session)):
    job, project = _load(job_id, session)
    return {
        "job_id": job_id,
        "report_url": f"/api/reports/{job_id}",
        "format": "html",
        "note": "Beta renders branded HTML (print to PDF). WeasyPrint PDF is the production path.",
    }

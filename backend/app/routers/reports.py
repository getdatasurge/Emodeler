"""Report generation (spec Ch 10.5). Beta returns branded HTML (printable to
PDF); production swaps in WeasyPrint server-side rendering."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import CalculationJob, Project
from ..report import render_report_html, render_report_pdf
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


@router.get("/api/reports/{job_id}/pdf")
def get_report_pdf(job_id: str, session: Session = Depends(get_session)):
    """Canonical server-side PDF. Degrades to 503 where the native PDF libs
    aren't installed (slim API image); the HTML report is always available."""
    job, project = _load(job_id, session)
    try:
        pdf = render_report_pdf(_serialize(project), job.comparison)
    except Exception as exc:  # noqa: BLE001 - WeasyPrint/native libs unavailable
        raise HTTPException(
            status_code=503,
            detail={"error": "PDF rendering unavailable in this deployment; use the HTML report",
                    "code": "PDF_UNAVAILABLE", "details": {"reason": type(exc).__name__}},
        ) from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="energy-report-{job_id}.pdf"'},
    )


@router.post("/api/reports/{job_id}")
def generate_report(job_id: str, session: Session = Depends(get_session)):
    job, project = _load(job_id, session)
    return {
        "job_id": job_id,
        "report_url": f"/api/reports/{job_id}",
        "report_pdf_url": f"/api/reports/{job_id}/pdf",
        "format": "html",
        "note": "HTML report is always available; /pdf renders the canonical PDF where the native libs are installed.",
    }

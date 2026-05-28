"""Project / faces / scenarios CRUD (spec Ch 10.1)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import lookups
from ..db import get_session
from ..models import CalculationJob, Face, Project, Scenario
from ..schemas_api import FaceIn, ProjectCreate, ProjectUpdate, ScenarioIn

router = APIRouter(tags=["projects"])


def _serialize(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "customer_name": project.customer_name,
        "address_line1": project.address_line1,
        "city": project.city,
        "state": project.state,
        "zip": project.zip,
        "latitude": project.latitude,
        "longitude": project.longitude,
        "climate_zone": project.climate_zone,
        "building_type": project.building_type,
        "gross_floor_area_sf": project.gross_floor_area_sf,
        "utility_label": project.utility_label,
        "utility_rate_usd_kwh": project.utility_rate_usd_kwh,
        "utility_rate_source": project.utility_rate_source,
        "egrid_subregion": project.egrid_subregion,
        "status": project.status,
        "faces": [
            {"id": f.id, "orientation": f.orientation, "area_sqft": f.area_sqft,
             "base_glazing_id": f.base_glazing_id, "count": f.count, "notes": f.notes}
            for f in project.faces
        ],
        "scenarios": [
            {"id": s.id, "label": s.label, "film_sku": s.film_sku,
             "installed_cost_usd": s.installed_cost_usd}
            for s in project.scenarios
        ],
    }


@router.post("/api/projects", status_code=201)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)):
    z = lookups.resolve_zip(body.zip)
    climate_zone = body.climate_zone or (z["climate_zone"] if z else None)
    if not climate_zone:
        raise HTTPException(status_code=422, detail={
            "error": "climate_zone required (ZIP not in crosswalk)",
            "code": "VALIDATION_FAILED", "details": {"zip": body.zip}})

    egrid_subregion = body.egrid_subregion or lookups.egrid_for_zip(body.zip)["subregion"]
    utility_rate = body.utility_rate_usd_kwh
    rate_source = "user_override" if body.utility_rate_usd_kwh else "urdb_default"
    if utility_rate is None:
        utility_rate = lookups.utility_for_zip(body.zip)["avg_energy_rate_usd_kwh"]

    project = Project(
        name=body.name, customer_name=body.customer_name, address_line1=body.address_line1,
        city=body.city, state=body.state, zip=body.zip,
        latitude=(z["lat"] if z else None), longitude=(z["lon"] if z else None),
        climate_zone=climate_zone, building_type=body.building_type,
        gross_floor_area_sf=body.gross_floor_area_sf,
        utility_rate_usd_kwh=utility_rate, utility_rate_source=rate_source,
        egrid_subregion=egrid_subregion,
    )
    for f in body.faces:
        project.faces.append(Face(orientation=f.orientation, area_sqft=f.area_sqft,
                                  base_glazing_id=f.base_glazing_id, count=f.count, notes=f.notes))
    for s in body.scenarios:
        project.scenarios.append(Scenario(label=s.label, film_sku=s.film_sku,
                                          installed_cost_usd=s.installed_cost_usd))
    session.add(project)
    session.commit()
    return _serialize(project)


@router.get("/api/projects")
def list_projects(session: Session = Depends(get_session)):
    projects = session.query(Project).order_by(Project.created_at.desc()).all()
    return [{"id": p.id, "name": p.name, "customer_name": p.customer_name, "zip": p.zip,
             "building_type": p.building_type, "status": p.status,
             "climate_zone": p.climate_zone} for p in projects]


@router.get("/api/projects/{project_id}")
def get_project(project_id: str, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    return _serialize(project)


@router.get("/api/projects/{project_id}/results")
def get_project_results(project_id: str, session: Session = Depends(get_session)):
    """Latest completed calculation comparison for a project."""
    job = (
        session.query(CalculationJob)
        .filter(CalculationJob.project_id == project_id, CalculationJob.status == "completed")
        .order_by(CalculationJob.completed_at.desc())
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "No completed analysis",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    return {"job_id": job.id, "engine_mode": job.engine_mode, "comparison": job.comparison}


@router.patch("/api/projects/{project_id}")
def update_project(project_id: str, body: ProjectUpdate, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    session.commit()
    return _serialize(project)


@router.post("/api/projects/{project_id}/faces", status_code=201)
def add_face(project_id: str, body: FaceIn, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    face = Face(project_id=project_id, orientation=body.orientation, area_sqft=body.area_sqft,
                base_glazing_id=body.base_glazing_id, count=body.count, notes=body.notes)
    session.add(face)
    session.commit()
    return _serialize(project)


@router.post("/api/scenarios", status_code=201)
def add_scenario(body: ScenarioIn, project_id: str, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    scenario = Scenario(project_id=project_id, label=body.label, film_sku=body.film_sku,
                        installed_cost_usd=body.installed_cost_usd)
    session.add(scenario)
    session.commit()
    return _serialize(project)

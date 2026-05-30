"""Project / faces / scenarios CRUD (spec Ch 10.1)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from energy_modeler.engine.inputs import BUILDING_FIELDS
from energy_modeler.parser.survey_xlsx import (
    collapse_to_single_project,
    group_by_building,
    parse_survey_xlsx,
)

from .. import lookups
from ..auth import Identity, require_auth
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
        "gas_rate_usd_therm": project.gas_rate_usd_therm,
        "egrid_subregion": project.egrid_subregion,
        **{k: getattr(project, k) for k in BUILDING_FIELDS},
        "status": project.status,
        "faces": [
            {"id": f.id, "orientation": f.orientation, "area_sqft": f.area_sqft,
             "base_glazing_id": f.base_glazing_id, "count": f.count,
             "tilt_deg": f.tilt_deg, "notes": f.notes}
            for f in project.faces
        ],
        "scenarios": [
            {"id": s.id, "label": s.label, "film_sku": s.film_sku,
             "installed_cost_usd": s.installed_cost_usd}
            for s in project.scenarios
        ],
    }


@router.post("/api/projects", status_code=201)
def create_project(
    body: ProjectCreate,
    session: Session = Depends(get_session),
    identity: Identity = Depends(require_auth),
):
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
        org_id=identity.org_id,
        name=body.name, customer_name=body.customer_name, address_line1=body.address_line1,
        city=body.city, state=body.state, zip=body.zip,
        latitude=(z["lat"] if z else None), longitude=(z["lon"] if z else None),
        climate_zone=climate_zone, building_type=body.building_type,
        gross_floor_area_sf=body.gross_floor_area_sf,
        utility_rate_usd_kwh=utility_rate, utility_rate_source=rate_source,
        gas_rate_usd_therm=body.gas_rate_usd_therm,
        egrid_subregion=egrid_subregion,
    )
    for k in BUILDING_FIELDS:
        setattr(project, k, getattr(body, k))
    for f in body.faces:
        project.faces.append(Face(orientation=f.orientation, area_sqft=f.area_sqft,
                                  base_glazing_id=f.base_glazing_id, count=f.count,
                                  tilt_deg=f.tilt_deg, notes=f.notes))
    for s in body.scenarios:
        project.scenarios.append(Scenario(label=s.label, film_sku=s.film_sku,
                                          installed_cost_usd=s.installed_cost_usd))
    session.add(project)
    session.commit()
    return _serialize(project)


@router.get("/api/projects")
def list_projects(
    session: Session = Depends(get_session),
    identity: Identity = Depends(require_auth),
):
    """Scoped to the caller's org. Single-tenant beta keeps the default
    DEFAULT_ORG_ID, so everyone sees everything until AUTH_ENFORCED is set
    and per-org JWTs start flowing."""
    projects = (
        session.query(Project)
        .filter(Project.org_id == identity.org_id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [{"id": p.id, "name": p.name, "customer_name": p.customer_name, "zip": p.zip,
             "building_type": p.building_type, "status": p.status,
             "climate_zone": p.climate_zone} for p in projects]


@router.get("/api/projects/{project_id}")
def get_project(
    project_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(require_auth),
):
    project = session.get(Project, project_id)
    if project is None or project.org_id != identity.org_id:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    return _serialize(project)


@router.get("/api/projects/{project_id}/results")
def get_project_results(
    project_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(require_auth),
):
    """Latest completed calculation comparison for a project."""
    project = session.get(Project, project_id)
    if project is None or project.org_id != identity.org_id:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
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
def update_project(
    project_id: str,
    body: ProjectUpdate,
    session: Session = Depends(get_session),
    identity: Identity = Depends(require_auth),
):
    project = session.get(Project, project_id)
    if project is None or project.org_id != identity.org_id:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    session.commit()
    return _serialize(project)


@router.post("/api/projects/{project_id}/faces", status_code=201)
def add_face(
    project_id: str,
    body: FaceIn,
    session: Session = Depends(get_session),
    identity: Identity = Depends(require_auth),
):
    project = session.get(Project, project_id)
    if project is None or project.org_id != identity.org_id:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    face = Face(project_id=project_id, orientation=body.orientation, area_sqft=body.area_sqft,
                base_glazing_id=body.base_glazing_id, count=body.count,
                tilt_deg=body.tilt_deg, notes=body.notes)
    session.add(face)
    session.commit()
    return _serialize(project)


@router.post("/api/projects/{project_id}/import-survey-xlsx", status_code=201)
async def import_survey_xlsx(
    project_id: str,
    file: UploadFile = File(...),
    mode: str = Query("replace", pattern="^(replace|append)$"),
    units: str = Query("in", pattern="^(in|ft)$"),
    session: Session = Depends(get_session),
    identity: Identity = Depends(require_auth),
):
    """Ingest a 3M/IWFA survey workbook and aggregate windows by Compass into
    faces. `mode=replace` (default) clears existing faces first; `mode=append`
    adds to them. `units=in` (default) treats W/H columns as inches."""
    project = session.get(Project, project_id)
    if project is None or project.org_id != identity.org_id:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    content = await file.read()
    try:
        rows = parse_survey_xlsx(content, units=units)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail={
            "error": str(exc), "code": "SURVEY_PARSE_FAILED",
            "details": {"filename": file.filename}}) from exc
    if not rows:
        raise HTTPException(status_code=422, detail={
            "error": "No usable rows found in survey sheet (need Compass + W + H per row).",
            "code": "SURVEY_EMPTY", "details": {"filename": file.filename}})

    # Single-project mode: collapse across the building dimension so a portfolio
    # workbook still produces one face per (orientation × glazing) for THIS
    # project. Use /api/projects/import-survey-portfolio to split per building.
    rows = collapse_to_single_project(rows)

    if mode == "replace":
        for f in list(project.faces):
            session.delete(f)
        session.flush()
    note = f"Imported from {file.filename}" if file.filename else "Imported from survey sheet"
    for r in rows:
        project.faces.append(Face(
            orientation=r.orientation, area_sqft=r.area_sqft,
            base_glazing_id=r.base_glazing_id, count=r.count,
            notes=f"{note} · {r.notes}" if r.notes else note,
        ))
    session.commit()
    return {
        "imported": len(rows),
        "mode": mode,
        "units": units,
        "project": _serialize(project),
    }


@router.post("/api/projects/import-survey-portfolio", status_code=201)
async def import_survey_portfolio(
    file: UploadFile = File(...),
    zip: str = Query(..., min_length=5, max_length=10),  # noqa: A002 (matches Project field)
    building_type: str = Query(...),
    gross_floor_area_sf: float = Query(..., gt=0),
    climate_zone: str | None = Query(None),
    units: str = Query("in", pattern="^(in|ft)$"),
    name_prefix: str = Query(""),
    session: Session = Depends(get_session),
    identity: Identity = Depends(require_auth),
):
    """Create one Project per Building ID found in the survey workbook.

    The template (zip / building_type / gross_floor_area_sf / climate_zone) is
    applied to every created project; tune per-project after import. Useful for
    a multi-school district uploaded as a single workbook (e.g. Millstone +
    New Brunswick + Evesham). Returns the list of created project ids."""
    content = await file.read()
    try:
        rows = parse_survey_xlsx(content, units=units)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail={
            "error": str(exc), "code": "SURVEY_PARSE_FAILED",
            "details": {"filename": file.filename}}) from exc
    if not rows:
        raise HTTPException(status_code=422, detail={
            "error": "No usable rows found in survey sheet (need Compass + W + H per row).",
            "code": "SURVEY_EMPTY", "details": {"filename": file.filename}})

    by_building = group_by_building(rows)
    z = lookups.resolve_zip(zip)
    cz = climate_zone or (z.get("climate_zone") if z else None)
    if not cz:
        raise HTTPException(status_code=422, detail={
            "error": "climate_zone required (ZIP not in crosswalk)",
            "code": "VALIDATION_FAILED", "details": {"zip": zip}})
    egrid = lookups.egrid_for_zip(zip)["subregion"]
    utility = lookups.utility_for_zip(zip)["avg_energy_rate_usd_kwh"]
    note = f"Imported from {file.filename}" if file.filename else "Imported from survey sheet"

    created: list[dict] = []
    for building_id, building_rows in by_building.items():
        proj_name = f"{name_prefix}{building_id}" if name_prefix else building_id
        project = Project(
            org_id=identity.org_id,
            name=proj_name, zip=zip,
            latitude=(z["lat"] if z else None), longitude=(z["lon"] if z else None),
            climate_zone=cz, building_type=building_type,
            gross_floor_area_sf=gross_floor_area_sf,
            utility_rate_usd_kwh=utility, utility_rate_source="urdb_default",
            egrid_subregion=egrid,
        )
        for r in building_rows:
            project.faces.append(Face(
                orientation=r.orientation, area_sqft=r.area_sqft,
                base_glazing_id=r.base_glazing_id, count=r.count,
                notes=f"{note} · {r.notes}" if r.notes else note,
            ))
        session.add(project)
        session.flush()
        created.append({
            "id": project.id, "name": project.name,
            "faces_imported": len(building_rows),
        })
    session.commit()
    return {
        "created": len(created),
        "units": units,
        "projects": created,
    }


@router.post("/api/scenarios", status_code=201)
def add_scenario(
    body: ScenarioIn,
    project_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(require_auth),
):
    project = session.get(Project, project_id)
    if project is None or project.org_id != identity.org_id:
        raise HTTPException(status_code=404, detail={"error": "Project not found",
                            "code": "NOT_FOUND", "details": {"project_id": project_id}})
    scenario = Scenario(project_id=project_id, label=body.label, film_sku=body.film_sku,
                        installed_cost_usd=body.installed_cost_usd)
    session.add(scenario)
    session.commit()
    return _serialize(project)

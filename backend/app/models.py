"""ORM models (spec Ch 9.3). Single-tenant beta; org_id present for the Phase 4
multi-tenant migration. Reference data (films, base glazings) is served from the
bundled datastore rather than the DB."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String, default=DEFAULT_ORG_ID, index=True)
    created_by: Mapped[str | None] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String)
    address_line1: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String)
    zip: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    climate_zone: Mapped[str] = mapped_column(String, nullable=False)
    building_type: Mapped[str] = mapped_column(String, nullable=False)
    gross_floor_area_sf: Mapped[float] = mapped_column(Float, nullable=False)
    utility_label: Mapped[str | None] = mapped_column(String)
    utility_rate_usd_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    utility_rate_source: Mapped[str] = mapped_column(String, default="urdb")
    # Optional gas rate ($/therm); when set, heating-gas savings are priced.
    gas_rate_usd_therm: Mapped[float | None] = mapped_column(Float)
    egrid_subregion: Mapped[str] = mapped_column(String, nullable=False)
    # As-built building characterization (spec Ch 5.3). All optional: blank
    # values fall back to prototype / climate-zone defaults at calc time.
    hvac_cooling_cop: Mapped[float | None] = mapped_column(Float)
    hvac_heating_cop: Mapped[float | None] = mapped_column(Float)
    hvac_system_type: Mapped[str | None] = mapped_column(String)
    hvac_fan_kw_per_cfm: Mapped[float | None] = mapped_column(Float)
    hvac_economizer_high_limit_f: Mapped[float | None] = mapped_column(Float)
    wall_area_sf: Mapped[float | None] = mapped_column(Float)
    wall_u_factor: Mapped[float | None] = mapped_column(Float)
    wall_absorptance: Mapped[float | None] = mapped_column(Float)
    roof_area_sf: Mapped[float | None] = mapped_column(Float)
    roof_type: Mapped[str | None] = mapped_column(String)
    roof_u_factor: Mapped[float | None] = mapped_column(Float)
    roof_absorptance: Mapped[float | None] = mapped_column(Float)
    operating_hours_per_week: Mapped[float | None] = mapped_column(Float)
    num_floors: Mapped[int | None] = mapped_column(Integer)
    floor_to_floor_ft: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    faces: Mapped[list["Face"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scenarios: Mapped[list["Scenario"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Face(Base):
    __tablename__ = "faces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    orientation: Mapped[str] = mapped_column(String, nullable=False)  # 8-point: N NE E SE S SW W NW + H
    area_sqft: Mapped[float] = mapped_column(Float, nullable=False)
    base_glazing_id: Mapped[str] = mapped_column(String, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=1)
    # Optional surface tilt (deg); None -> use the orientation's default (vertical
    # for cardinals/intercardinals, horizontal for H).
    tilt_deg: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[Project] = relationship(back_populates="faces")


class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String, nullable=False)
    film_sku: Mapped[str] = mapped_column(String, nullable=False)
    installed_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[Project] = relationship(back_populates="scenarios")


class CalculationJob(Base):
    __tablename__ = "calculation_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String, default="queued")  # queued running completed failed
    engine_mode: Mapped[str | None] = mapped_column(String)
    energyplus_version: Mapped[str | None] = mapped_column(String)
    weather_station: Mapped[str | None] = mapped_column(String)
    scenarios_total: Mapped[int] = mapped_column(Integer, default=0)
    scenarios_completed: Mapped[int] = mapped_column(Integer, default=0)
    comparison: Mapped[dict | None] = mapped_column(JSON)  # ProjectComparison.model_dump
    audit_bundle_path: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_phase: Mapped[str | None] = mapped_column(String)
    options: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ========== auth & orgs (spec Ch 9.3; single-tenant beta, multi-tenant ready) ==========


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)  # = auth.users(id) in prod
    org_id: Mapped[str] = mapped_column(String, default=DEFAULT_ORG_ID, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="analyst")  # owner|admin|analyst|viewer
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ========== reference catalogs ==========


class BaseGlazing(Base):
    __tablename__ = "base_glazings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    layer_count: Mapped[int] = mapped_column(Integer, default=1)
    u_factor_btuhrft2F: Mapped[float] = mapped_column(Float, nullable=False)
    shgc: Mapped[float] = mapped_column(Float, nullable=False)
    vt: Mapped[float] = mapped_column(Float, nullable=False)
    igsdb_construction: Mapped[list] = mapped_column(JSON, default=list)


class FilmGlassPairing(Base):
    __tablename__ = "film_glass_pairings"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    film_sku: Mapped[str] = mapped_column(String, index=True, nullable=False)
    base_glazing_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    shgc: Mapped[float] = mapped_column(Float, nullable=False)
    u_btu_h_ft2_F: Mapped[float] = mapped_column(Float, nullable=False)
    vt: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String, default="igsdb")  # igsdb|lbnl_window_8_local|manufacturer
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ========== calculation results + audit trail ==========


class ScenarioResult(Base):
    __tablename__ = "scenario_results"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("calculation_jobs.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str | None] = mapped_column(String)  # NULL for baseline
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    is_appendix_g_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    annual_end_uses: Mapped[dict] = mapped_column(JSON, default=dict)
    peak_demand: Mapped[dict] = mapped_column(JSON, default=dict)
    windows: Mapped[list] = mapped_column(JSON, default=list)
    delta_total_kwh: Mapped[float | None] = mapped_column(Float)
    delta_cooling_kwh: Mapped[float | None] = mapped_column(Float)
    delta_heating_kwh: Mapped[float | None] = mapped_column(Float)
    delta_peak_kw: Mapped[float | None] = mapped_column(Float)
    delta_cost_usd_yr: Mapped[float | None] = mapped_column(Float)
    delta_co2_lb_yr: Mapped[float | None] = mapped_column(Float)
    simple_payback_yrs: Mapped[float | None] = mapped_column(Float)
    npv_15yr_usd: Mapped[float | None] = mapped_column(Float)
    irr_15yr_pct: Mapped[float | None] = mapped_column(Float)
    raw_eplus_output_url: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class FilmRecordHistory(Base):
    __tablename__ = "film_record_history"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    film_sku: Mapped[str] = mapped_column(String, index=True, nullable=False)
    igsdb_product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    changed: Mapped[bool] = mapped_column(Boolean, default=False)
    diff_summary: Mapped[dict | None] = mapped_column(JSON)


class ZipLookupCache(Base):
    __tablename__ = "zip_lookup_cache"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    zip: Mapped[str] = mapped_column(String, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # solar|utility|climate_zone|egrid
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String, default=DEFAULT_ORG_ID, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_table: Mapped[str | None] = mapped_column(String)
    target_id: Mapped[str | None] = mapped_column(String)
    payload: Mapped[dict | None] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)

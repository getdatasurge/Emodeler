"""ORM models (spec Ch 9.3). Single-tenant beta; org_id present for the Phase 4
multi-tenant migration. Reference data (films, base glazings) is served from the
bundled datastore rather than the DB."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
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
    egrid_subregion: Mapped[str] = mapped_column(String, nullable=False)
    # As-built building characterization (spec Ch 5.3). All optional: blank
    # values fall back to prototype / climate-zone defaults at calc time.
    hvac_cooling_cop: Mapped[float | None] = mapped_column(Float)
    hvac_heating_cop: Mapped[float | None] = mapped_column(Float)
    hvac_system_type: Mapped[str | None] = mapped_column(String)
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
    orientation: Mapped[str] = mapped_column(String, nullable=False)  # N S E W H
    area_sqft: Mapped[float] = mapped_column(Float, nullable=False)
    base_glazing_id: Mapped[str] = mapped_column(String, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=1)
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

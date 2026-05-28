"""Request/response models for the REST API (spec Ch 10)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FaceIn(BaseModel):
    orientation: str = Field(pattern="^[NSEWH]$")
    area_sqft: float = Field(gt=0)
    base_glazing_id: str
    count: int = 1
    notes: str | None = None


class ScenarioIn(BaseModel):
    label: str
    film_sku: str
    installed_cost_usd: float = Field(ge=0)


class ProjectCreate(BaseModel):
    name: str
    customer_name: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str
    building_type: str
    gross_floor_area_sf: float = Field(gt=0)
    # Optional — auto-filled from ZIP when omitted.
    climate_zone: str | None = None
    utility_rate_usd_kwh: float | None = None
    egrid_subregion: str | None = None
    faces: list[FaceIn] = Field(default_factory=list)
    scenarios: list[ScenarioIn] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: str | None = None
    customer_name: str | None = None
    gross_floor_area_sf: float | None = None
    utility_rate_usd_kwh: float | None = None
    status: str | None = None


class CalcOptions(BaseModel):
    film_life_yrs: int = 15
    discount_rate: float = 0.05
    utility_escalation: float = 0.025
    include_appendix_g_baseline: bool = False
    include_demand_charge: bool = False


class CalcRunRequest(BaseModel):
    project_id: str
    scenarios: list[ScenarioIn] = Field(default_factory=list)
    options: CalcOptions = Field(default_factory=CalcOptions)

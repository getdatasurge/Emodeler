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


class BuildingInputs(BaseModel):
    """Optional as-built building characterization (spec Ch 5.3). Blank values
    fall back to prototype / climate-zone defaults at calc time."""
    hvac_cooling_cop: float | None = Field(default=None, gt=0, le=10)
    hvac_heating_cop: float | None = Field(default=None, gt=0, le=10)
    hvac_system_type: str | None = None
    wall_area_sf: float | None = Field(default=None, ge=0)
    wall_u_factor: float | None = Field(default=None, gt=0, le=2)
    wall_absorptance: float | None = Field(default=None, ge=0, le=1)
    roof_area_sf: float | None = Field(default=None, ge=0)
    roof_type: str | None = None
    roof_u_factor: float | None = Field(default=None, gt=0, le=2)
    roof_absorptance: float | None = Field(default=None, ge=0, le=1)
    operating_hours_per_week: float | None = Field(default=None, gt=0, le=168)
    num_floors: int | None = Field(default=None, ge=1, le=200)
    floor_to_floor_ft: float | None = Field(default=None, gt=0, le=50)


class ProjectCreate(BuildingInputs):
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


class ProjectUpdate(BuildingInputs):
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

"""Unified result schema (spec Ch 6.3). One EnergyPlus run -> RunResult; a full
project analysis -> N+1 RunResults plus a ProjectComparison with per-film deltas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EnergyEndUses(BaseModel):
    heating_elec_kwh: float = 0.0
    heating_gas_kwh: float = 0.0
    cooling_elec_kwh: float = 0.0
    interior_lighting_kwh: float = 0.0
    interior_equipment_kwh: float = 0.0
    fans_kwh: float = 0.0
    pumps_kwh: float = 0.0
    heat_rejection_kwh: float = 0.0
    total_electricity_kwh: float = 0.0
    total_gas_kwh: float = 0.0


class WindowSurfaceResult(BaseModel):
    surface_name: str
    orientation_deg: float  # 0=N, 90=E, 180=S, 270=W
    tilt_deg: float  # 90=vertical, 0=horizontal
    area_m2: float
    annual_solar_transmitted_kwh: float = 0.0
    annual_heat_gain_kwh: float = 0.0
    annual_heat_loss_kwh: float = 0.0
    peak_heat_gain_rate_w: float = 0.0


class PeakDemand(BaseModel):
    total_facility_peak_kw: float = 0.0
    cooling_peak_kw: float = 0.0


class RunResult(BaseModel):
    run_id: str
    scenario_label: str  # 'baseline' | film SKU / tier label
    engine_mode: str  # 'energyplus' | 'analytical_estimate'
    energyplus_version: str
    weather_station: str
    weather_dataset: str
    annual_end_uses: EnergyEndUses
    peak_demand: PeakDemand
    windows: list[WindowSurfaceResult] = Field(default_factory=list)
    sim_runtime_seconds: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class FilmComparison(BaseModel):
    scenario_label: str
    film_sku: str
    delta_cooling_kwh: float  # baseline - film (positive = savings)
    delta_heating_kwh: float  # negative usually (winter penalty)
    delta_lighting_kwh: float = 0.0
    delta_total_kwh: float
    delta_peak_kw: float
    delta_cost_usd_per_year: float
    delta_co2_lb_per_year: float
    delta_co2e_kg_per_year: float = 0.0
    project_cost_usd: float
    simple_payback_years: float
    npv_15yr_usd: float
    irr_15yr_pct: float


class ProjectComparison(BaseModel):
    project_id: str
    engine_mode: str
    baseline: RunResult
    films: list[FilmComparison] = Field(default_factory=list)
    film_runs: list[RunResult] = Field(default_factory=list)
    # Resolved as-built building characterization (HVAC/envelope/ops) with a
    # per-field 'user' | 'default' provenance map, for the inputs/audit display.
    building: dict | None = None
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)
    audit_bundle_path: str | None = None

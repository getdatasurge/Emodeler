"""Engine-facing project input types. The API/pipeline layer maps database
records onto these so the engine has no dependency on the persistence layer."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EngineFace:
    # 8-point compass plus horizontal (skylights): N | NE | E | SE | S | SW | W | NW | H.
    # Surveyors record at intercardinals (per the 3M/IWFA survey sheet); keeping
    # that fidelity matters because SW catches the afternoon cooling peak.
    orientation: str
    area_sqft: float
    base_glazing_id: str


@dataclass
class EngineScenario:
    label: str
    film_sku: str
    installed_cost_usd: float


@dataclass
class EngineOptions:
    film_life_yrs: int = 15
    discount_rate: float = 0.05
    utility_escalation: float = 0.025
    include_appendix_g_baseline: bool = False
    include_demand_charge: bool = False
    demand_charge_usd_per_kw: float = 0.0
    # Prototype-to-project rescale basis: 'floor' (matches EFILM, default) or
    # 'glazing' (project glazing area / prototype glazing area — more physical
    # for window-film savings since the delta is glazing-area-driven).
    # parser_bridge stamps BOTH factors onto the run's warnings either way.
    scaling_basis: str = "floor"


@dataclass
class EngineProject:
    project_id: str
    building_type: str
    climate_zone: str
    gross_floor_area_sf: float
    zip: str
    utility_rate_usd_kwh: float
    egrid_subregion: str
    # Optional gas rate ($/therm). When set, heating-gas savings are priced
    # separately; otherwise gas savings contribute $0 (the prior behavior, fine
    # for all-electric buildings but materially wrong for gas-heated cold-climate
    # projects).
    gas_rate_usd_therm: float | None = None
    faces: list[EngineFace] = field(default_factory=list)
    scenarios: list[EngineScenario] = field(default_factory=list)
    options: EngineOptions = field(default_factory=EngineOptions)

    # As-built building characterization (spec Ch 5.3). All optional: blank
    # values fall back to prototype / climate-zone defaults via engine.building.
    # HVAC
    hvac_cooling_cop: float | None = None
    hvac_heating_cop: float | None = None
    hvac_system_type: str | None = None
    # Supply-fan electrical power per CFM (kW/CFM). Reducing solar load via
    # film also cuts fan work — modeling this correctly matters for the
    # cooling savings number a PE will sign off. Typical commercial DOAS / VAV
    # ~0.0005-0.001 kW/CFM. When set, the IDF mutator adjusts each Fan:*
    # object's Pressure_Rise to achieve the target while preserving its
    # Fan_Total_Efficiency.
    hvac_fan_kw_per_cfm: float | None = None
    # Opaque envelope
    wall_area_sf: float | None = None
    wall_u_factor: float | None = None
    wall_absorptance: float | None = None
    roof_area_sf: float | None = None
    roof_type: str | None = None
    roof_u_factor: float | None = None
    roof_absorptance: float | None = None
    # Operations & geometry
    operating_hours_per_week: float | None = None
    num_floors: int | None = None
    floor_to_floor_ft: float | None = None


# Canonical building-characterization field names, shared by the ORM model, the
# API schema, and the persistence -> engine mapping so they can't drift.
BUILDING_FIELDS: tuple[str, ...] = (
    "hvac_cooling_cop",
    "hvac_heating_cop",
    "hvac_system_type",
    "hvac_fan_kw_per_cfm",
    "wall_area_sf",
    "wall_u_factor",
    "wall_absorptance",
    "roof_area_sf",
    "roof_type",
    "roof_u_factor",
    "roof_absorptance",
    "operating_hours_per_week",
    "num_floors",
    "floor_to_floor_ft",
)

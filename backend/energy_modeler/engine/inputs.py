"""Engine-facing project input types. The API/pipeline layer maps database
records onto these so the engine has no dependency on the persistence layer."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EngineFace:
    orientation: str  # 'N' | 'S' | 'E' | 'W' | 'H'
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


@dataclass
class EngineProject:
    project_id: str
    building_type: str
    climate_zone: str
    gross_floor_area_sf: float
    zip: str
    utility_rate_usd_kwh: float
    egrid_subregion: str
    faces: list[EngineFace] = field(default_factory=list)
    scenarios: list[EngineScenario] = field(default_factory=list)
    options: EngineOptions = field(default_factory=EngineOptions)

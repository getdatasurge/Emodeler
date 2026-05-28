"""Building characterization: resolve as-built HVAC / envelope / operations
inputs against prototype + climate-zone defaults.

User-supplied values always win; anything left blank falls back to the DOE
prototype aggregate or an ASHRAE 90.1-2019 climate-zone baseline. The analytical
estimator uses the resolved HVAC COP (the dominant lever on $ savings) and the
glazing U-factor for per-window conduction; the full envelope (wall/roof area,
U-factor, solar absorptance) and operating schedule are carried through to the
EnergyPlus engine, which actually simulates them (spec Ch 4-5)."""
from __future__ import annotations

import math
from dataclasses import dataclass

BTU_PER_KWH = 3412.14
SF_TO_M2 = 0.092903

# Heating/cooling degree days (base 65 deg F, deg F-days), proxied by the leading
# digit of the ASHRAE climate zone. Used only for opaque/window conduction.
DEGREE_DAYS: dict[str, tuple[float, float]] = {  # (HDD65, CDD65)
    "1": (150, 4000),
    "2": (800, 3000),
    "3": (1800, 1900),
    "4": (3700, 1200),
    "5": (5400, 900),
    "6": (7200, 600),
    "7": (9000, 400),
    "8": (12000, 200),
}

# ASHRAE 90.1-2019 prescriptive opaque U-factors (BTU/hr.ft2.F), by zone digit.
WALL_U_DEFAULT = {"1": 0.104, "2": 0.084, "3": 0.064, "4": 0.064,
                  "5": 0.064, "6": 0.051, "7": 0.051, "8": 0.045}
ROOF_U_DEFAULT = {"1": 0.039, "2": 0.039, "3": 0.039, "4": 0.032,
                  "5": 0.032, "6": 0.032, "7": 0.028, "8": 0.028}

DEFAULT_OPERATING_HOURS = 55.0
DEFAULT_FLOOR_TO_FLOOR_FT = 13.0
DEFAULT_WALL_ABSORPTANCE = 0.60  # medium-tone masonry/EIFS
DEFAULT_ROOF_ABSORPTANCE = 0.70  # aged dark membrane (cool roof ~0.30)

# Representative cooling-design peak transmitted irradiance by orientation (W/m2).
# West peaks highest (afternoon coincident with the cooling peak); north lowest.
PEAK_POA_W_M2 = {"S": 480.0, "E": 620.0, "W": 700.0, "N": 180.0, "H": 880.0}


def zone_digit(climate_zone: str | None) -> str:
    return (climate_zone or "4")[:1]


def conduction_kwh(u_btuhrft2F: float, area_sf: float, degree_days: float) -> float:
    """Annual conductive energy through a surface: U * A * DD * 24h / (BTU/kWh)."""
    return u_btuhrft2F * area_sf * degree_days * 24.0 / BTU_PER_KWH


def peak_poa(orientation: str) -> float:
    return PEAK_POA_W_M2.get(orientation, 500.0)


@dataclass
class ResolvedBuilding:
    cooling_cop: float
    heating_cop: float
    hvac_system_type: str
    num_floors: int
    floor_to_floor_ft: float
    wall_area_sf: float
    wall_u_factor: float
    wall_absorptance: float
    roof_area_sf: float
    roof_type: str
    roof_u_factor: float
    roof_absorptance: float
    operating_hours_per_week: float
    hdd65: float
    cdd65: float
    # Provenance: field name -> 'user' | 'default'. Drives the audit/inputs note.
    sources: dict[str, str]


def _pick(user_value, default_value, name: str, sources: dict[str, str]):
    if user_value is not None:
        sources[name] = "user"
        return user_value
    sources[name] = "default"
    return default_value


def resolve(project, proto: dict) -> ResolvedBuilding:
    """Resolve a project's building inputs against prototype + climate defaults.

    `project` is an EngineProject; `proto` is the datastore prototype dict."""
    zd = zone_digit(project.climate_zone)
    hdd, cdd = DEGREE_DAYS.get(zd, DEGREE_DAYS["4"])
    src: dict[str, str] = {}

    floors = int(_pick(project.num_floors, int(proto.get("floors", 1)), "num_floors", src) or 1)
    floors = max(1, floors)
    f2f = float(_pick(project.floor_to_floor_ft, DEFAULT_FLOOR_TO_FLOOR_FT, "floor_to_floor_ft", src))

    footprint_sf = max(project.gross_floor_area_sf / floors, 1.0)
    perimeter_ft = 4.0 * math.sqrt(footprint_sf)  # square-footprint assumption
    gross_wall_sf = perimeter_ft * f2f * floors
    total_window_sf = sum(f.area_sqft for f in project.faces)
    if total_window_sf <= 0:
        total_window_sf = float(proto.get("wwr", 0.3)) * gross_wall_sf
    opaque_wall_default = max(0.0, gross_wall_sf - total_window_sf)

    return ResolvedBuilding(
        cooling_cop=float(_pick(project.hvac_cooling_cop, float(proto.get("cop", 3.4)), "cooling_cop", src)),
        heating_cop=float(_pick(project.hvac_heating_cop, 3.0, "heating_cop", src)),
        hvac_system_type=str(_pick(project.hvac_system_type, "packaged_dx", "hvac_system_type", src)),
        num_floors=floors,
        floor_to_floor_ft=f2f,
        wall_area_sf=float(_pick(project.wall_area_sf, opaque_wall_default, "wall_area_sf", src)),
        wall_u_factor=float(_pick(project.wall_u_factor, WALL_U_DEFAULT.get(zd, 0.064), "wall_u_factor", src)),
        wall_absorptance=float(_pick(project.wall_absorptance, DEFAULT_WALL_ABSORPTANCE, "wall_absorptance", src)),
        roof_area_sf=float(_pick(project.roof_area_sf, footprint_sf, "roof_area_sf", src)),
        roof_type=str(_pick(project.roof_type, "membrane", "roof_type", src)),
        roof_u_factor=float(_pick(project.roof_u_factor, ROOF_U_DEFAULT.get(zd, 0.039), "roof_u_factor", src)),
        roof_absorptance=float(_pick(project.roof_absorptance, DEFAULT_ROOF_ABSORPTANCE, "roof_absorptance", src)),
        operating_hours_per_week=float(
            _pick(project.operating_hours_per_week, float(proto.get("operating_hours", DEFAULT_OPERATING_HOURS)),
                  "operating_hours_per_week", src)
        ),
        hdd65=float(hdd),
        cdd65=float(cdd),
        sources=src,
    )

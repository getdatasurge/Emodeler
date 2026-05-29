"""ASHRAE 90.1-2016 Appendix G baseline generation (spec Ch 5.5 / Ch 6.6).

The Appendix G "baseline building" is a prescriptively-defined reference used for
LEED EAc / PCI: baseline envelope (Table G3.4/G3.5), fenestration (G3.4), HVAC
system type (G3.1.1), and lighting power density (G3.1.6) for the project's
climate zone and size — independent of as-built. baseline_spec() resolves those
parameters (pure lookup, unit-tested); build_baseline_idf() applies them to a
prototype IDF via eppy for the EnergyPlus baseline run.

NOTE: the fenestration/LPD/system tables below are representative encodings of
the published Appendix G tables — verify against ASHRAE 90.1-2016 Appendix G
before relying on a PCI/LEED point count for a submission."""
from __future__ import annotations

from dataclasses import dataclass

from .building import ROOF_U_DEFAULT, WALL_U_DEFAULT, zone_digit

# Baseline vertical fenestration U (BTU/h.ft2.F) and SHGC by climate-zone digit
# (Table G3.4, fixed fenestration). Hot zones cap SHGC hard; cold zones relax it.
_WINDOW_U = {"1": 0.50, "2": 0.50, "3": 0.46, "4": 0.38, "5": 0.38, "6": 0.36, "7": 0.35, "8": 0.35}
_WINDOW_SHGC = {"1": 0.25, "2": 0.25, "3": 0.25, "4": 0.36, "5": 0.38, "6": 0.40, "7": 0.45, "8": 0.45}

# Baseline lighting power density (W/ft2) by building type (Table G3.1.6 / 9.5.1).
_LPD_W_SF = {
    "SmallOffice": 0.79, "MediumOffice": 0.79, "LargeOffice": 0.79,
    "PrimarySchool": 0.87, "SecondarySchool": 0.87,
    "StandaloneRetail": 1.06, "StripMall": 1.0, "Warehouse": 0.66,
}


def baseline_system_type(floors: int, area_sf: float) -> str:
    """Baseline HVAC system per Table G3.1.1 (nonresidential, fossil-fuel heat)."""
    if floors > 5 or area_sf > 150_000:
        return "System 7 — VAV w/ reheat (built-up)"
    if area_sf >= 25_000 or floors >= 4:
        return "System 5 — Packaged VAV w/ reheat"
    return "System 3 — PSZ-AC"


@dataclass
class BaselineSpec:
    climate_zone: str
    wall_u_factor: float
    roof_u_factor: float
    window_u_factor: float
    window_shgc: float
    lpd_w_sf: float
    hvac_system: str


def baseline_spec(building_type: str, climate_zone: str, floors: int, area_sf: float) -> BaselineSpec:
    zd = zone_digit(climate_zone)
    return BaselineSpec(
        climate_zone=climate_zone,
        wall_u_factor=WALL_U_DEFAULT.get(zd, 0.064),
        roof_u_factor=ROOF_U_DEFAULT.get(zd, 0.039),
        window_u_factor=_WINDOW_U.get(zd, 0.38),
        window_shgc=_WINDOW_SHGC.get(zd, 0.36),
        lpd_w_sf=_LPD_W_SF.get(building_type, 0.79),
        hvac_system=baseline_system_type(floors, area_sf),
    )


def build_baseline_idf(idf, spec: BaselineSpec):
    """Apply the Appendix G baseline to a loaded eppy prototype IDF: a
    SimpleGlazingSystem window at the baseline U/SHGC, and baseline LPD on every
    Lights object. (Opaque-envelope U and the prescribed HVAC system swap are
    layered on in the worker against the full prototype.) Returns the IDF."""
    from . import idf_ops

    idf.newidfobject(
        "WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM",
        Name="AppxG_Baseline_Window",
        UFactor=spec.window_u_factor * 5.678,  # IP -> SI (W/m2.K) for EnergyPlus
        Solar_Heat_Gain_Coefficient=spec.window_shgc,
    )
    con = idf.newidfobject("CONSTRUCTION", Name="AppxG_Baseline_Glazing")
    con.Outside_Layer = "AppxG_Baseline_Window"
    idf_ops.set_window_construction(idf, "AppxG_Baseline_Glazing")
    for lights in idf.idfobjects.get("LIGHTS", []):
        if hasattr(lights, "Watts_per_Zone_Floor_Area"):
            lights.Design_Level_Calculation_Method = "Watts/Area"
            lights.Watts_per_Zone_Floor_Area = spec.lpd_w_sf * 10.7639  # W/ft2 -> W/m2
    idf_ops.add_standard_outputs(idf)
    return idf

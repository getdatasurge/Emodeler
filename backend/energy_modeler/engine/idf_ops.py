"""eppy IDF-mutation primitives (spec Ch 5 / 7) for the real EnergyPlus pipeline.

These operate on a loaded DOE-prototype IDF to produce baseline + film scenario
IDFs. eppy is a worker-image dependency, imported lazily by callers; the helpers
themselves just take an eppy IDF object so they're unit-testable against any IDF.

Version-robust on purpose: object/field names drift across EnergyPlus releases,
so each helper tries the known aliases and reports how many objects it touched.
Validated against a synthetic IDF in tests; real DOE-prototype validation runs in
the worker image against the 22.1 binary (spec Ch 12)."""
from __future__ import annotations

from typing import Any

# DX cooling coils whose rated COP we pin to the as-built value. The retrofit
# rule (spec 0.4): installed HVAC efficiency is identical in baseline and film
# scenarios — we never resize or re-rate between them.
_COOLING_COIL_CLASSES = (
    "COIL:COOLING:DX:SINGLESPEED",
    "COIL:COOLING:DX:TWOSPEED",
    "COIL:COOLING:DX:MULTISPEED",
    "COIL:COOLING:DX:CURVEFIT:PERFORMANCE",
)
_COOLING_COP_FIELDS = (
    "Gross_Rated_Cooling_COP",
    "Rated_COP",
    "High_Speed_Gross_Rated_Cooling_COP",
    "Speed_1_Gross_Rated_Cooling_COP",
)
_HEATING_COIL_CLASSES = ("COIL:HEATING:DX:SINGLESPEED", "COIL:HEATING:DX:MULTISPEED")
_HEATING_COP_FIELDS = ("Gross_Rated_Heating_COP", "Rated_COP", "Speed_1_Gross_Rated_Heating_COP")

# Supply / return fan classes the kW/CFM rescaler touches.
_FAN_CLASSES = (
    "FAN:VARIABLEVOLUME",
    "FAN:CONSTANTVOLUME",
    "FAN:ONOFF",
    "FAN:SYSTEMMODEL",
)
# 1 CFM in m3/s.
_CFM_TO_M3S = 0.000471947


def _f_to_c(temp_f: float) -> float:
    return (temp_f - 32.0) * 5.0 / 9.0


def _set_first_present(obj: Any, fields: tuple[str, ...], value: float) -> bool:
    for f in fields:
        if hasattr(obj, f):
            setattr(obj, f, value)
            return True
    return False


def set_cooling_cop(idf: Any, cop: float) -> int:
    """Pin rated COP on every DX cooling coil. Returns the number of coils set."""
    n = 0
    for cls in _COOLING_COIL_CLASSES:
        for coil in idf.idfobjects.get(cls, []):
            if _set_first_present(coil, _COOLING_COP_FIELDS, cop):
                n += 1
    return n


def set_heating_cop(idf: Any, cop: float) -> int:
    """Pin rated COP on every DX heating coil. Returns the number of coils set."""
    n = 0
    for cls in _HEATING_COIL_CLASSES:
        for coil in idf.idfobjects.get(cls, []):
            if _set_first_present(coil, _HEATING_COP_FIELDS, cop):
                n += 1
    return n


def set_economizer_high_limit_f(idf: Any, high_limit_f: float) -> int:
    """Enable a fixed-dry-bulb economizer with the supplied high-limit
    temperature on every Controller:OutdoorAir. EnergyPlus stores the limit
    in degrees C; the user faces F (the building-engineer-friendly unit).

    No-op when high_limit_f is None / 0 / negative. Returns the number of
    controllers touched. Many DOE prototypes ship NoEconomizer (the 90.1
    minimum-compliant default) — flipping this on is one of the cheapest
    cooling-savings levers and a common as-built override."""
    if not high_limit_f or high_limit_f <= 0:
        return 0
    high_limit_c = round(_f_to_c(high_limit_f), 2)
    n = 0
    for ctrl in idf.idfobjects.get("CONTROLLER:OUTDOORAIR", []):
        existing = (getattr(ctrl, "Economizer_Control_Type", "") or "").strip()
        # Don't downgrade richer schemes (enthalpy / differential dry-bulb);
        # only enable when the prototype was "NoEconomizer".
        if existing.lower() in ("", "noeconomizer"):
            ctrl.Economizer_Control_Type = "FixedDryBulb"
        if hasattr(ctrl, "Economizer_Maximum_Limit_DryBulb_Temperature"):
            ctrl.Economizer_Maximum_Limit_DryBulb_Temperature = high_limit_c
            n += 1
        elif hasattr(ctrl, "Economizer_Maximum_Limit_Dry_Bulb_Temperature"):
            ctrl.Economizer_Maximum_Limit_Dry_Bulb_Temperature = high_limit_c
            n += 1
    return n


def set_fan_kw_per_cfm(idf: Any, kw_per_cfm: float) -> int:
    """Rescale every Fan:* object so its electrical power per CFM matches the
    target. Preserves Fan_Total_Efficiency by adjusting Pressure_Rise:

        W_per_m3s = Pressure_Rise / Fan_Total_Efficiency
        kW_per_CFM = W_per_m3s * 0.000471947 / 1000
    -> Pressure_Rise = kW_per_CFM * 1000 / 0.000471947 * Fan_Total_Efficiency

    Returns the number of fans touched. No-op when kw_per_cfm is None/<=0.
    """
    if not kw_per_cfm or kw_per_cfm <= 0:
        return 0
    target_w_per_m3s = (kw_per_cfm * 1000.0) / _CFM_TO_M3S
    n = 0
    for cls in _FAN_CLASSES:
        for fan in idf.idfobjects.get(cls, []):
            eff_raw = (
                getattr(fan, "Fan_Total_Efficiency", None)
                or getattr(fan, "Motor_Efficiency", None)
                or 0.6
            )
            try:
                eff = float(eff_raw) if eff_raw not in (None, "", "Autosize") else 0.6
            except (TypeError, ValueError):
                eff = 0.6
            new_pressure_rise = round(target_w_per_m3s * eff, 1)
            if hasattr(fan, "Pressure_Rise"):
                fan.Pressure_Rise = new_pressure_rise
                n += 1
            elif hasattr(fan, "Design_Pressure_Rise"):  # Fan:SystemModel
                fan.Design_Pressure_Rise = new_pressure_rise
                n += 1
    return n


def set_window_construction(idf: Any, construction_name: str) -> int:
    """Point every exterior window / glass door at `construction_name`. Returns
    the number of fenestration surfaces updated."""
    n = 0
    for surf in idf.idfobjects.get("FENESTRATIONSURFACE:DETAILED", []):
        if getattr(surf, "Surface_Type", "Window") in ("Window", "GlassDoor"):
            surf.Construction_Name = construction_name
            n += 1
    for surf in idf.idfobjects.get("WINDOW", []):
        surf.Construction_Name = construction_name
        n += 1
    return n


# DOE prototypes embed the elevation in the window's Name (e.g.
# 'Perimeter_bot_ZN_1_Wall_South_Window1'); we map that token back to a
# cardinal direction so per-face base glazings can be dispatched correctly.
_CARDINAL_TOKENS = {"S": "south", "N": "north", "E": "east", "W": "west"}


def _cardinal_from_window_name(name: str) -> str | None:
    name_l = (name or "").lower()
    for cardinal, token in _CARDINAL_TOKENS.items():
        if token in name_l:
            return cardinal
    return None


def set_window_construction_by_orientation(
    idf: Any, constructions_by_cardinal: dict[str, str]
) -> int:
    """Assign each exterior window the construction matching its cardinal
    elevation (parsed from the window's Name in DOE prototypes). Windows whose
    elevation can't be derived fall back to the 'DEFAULT' key. Returns the
    number of fenestration surfaces updated.

    Lets a project with mixed glass (e.g. tinted south, clear elsewhere)
    survive the prototype-window-construction swap instead of being collapsed
    to face[0]'s glazing.
    """
    default = constructions_by_cardinal.get("DEFAULT")
    n = 0
    for collection in ("FENESTRATIONSURFACE:DETAILED", "WINDOW"):
        for surf in idf.idfobjects.get(collection, []):
            if collection == "FENESTRATIONSURFACE:DETAILED" and getattr(
                surf, "Surface_Type", "Window"
            ) not in ("Window", "GlassDoor"):
                continue
            cardinal = _cardinal_from_window_name(getattr(surf, "Name", ""))
            con = constructions_by_cardinal.get(cardinal) if cardinal else default
            if con:
                surf.Construction_Name = con
                n += 1
    return n


# Output:Meter names the parser (Ch 6) needs; Heating:Gas was renamed
# Heating:NaturalGas in EnergyPlus 9.x — request both, harmless if one is absent.
_OUTPUT_METERS = (
    "Electricity:Facility",
    "Cooling:Electricity",
    "Heating:Electricity",
    "Heating:NaturalGas",
    "Fans:Electricity",
    "InteriorLights:Electricity",
)
# Energy (J) variants — eplusout.csv aggregates monthly to give a real
# accumulated quantity. The Rate variant (W) returns mean power, which the
# parser would have to multiply by hours-per-month, so we ask for Energy.
_OUTPUT_VARIABLES = (
    "Surface Window Heat Gain Energy",
    "Surface Window Heat Loss Energy",
    "Surface Window Transmitted Solar Radiation Energy",
)


def add_standard_outputs(idf: Any) -> None:
    """Add the Output:Meter / Output:Variable objects the parser needs (Ch 4.5)."""
    existing_meters = {getattr(m, "Key_Name", "") for m in idf.idfobjects.get("OUTPUT:METER", [])}
    for meter in _OUTPUT_METERS:
        if meter not in existing_meters:
            idf.newidfobject("OUTPUT:METER", Key_Name=meter, Reporting_Frequency="Monthly")
    for var in _OUTPUT_VARIABLES:
        idf.newidfobject(
            "OUTPUT:VARIABLE", Key_Value="*", Variable_Name=var, Reporting_Frequency="Monthly"
        )

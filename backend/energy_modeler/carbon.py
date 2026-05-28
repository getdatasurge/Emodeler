"""Carbon — CO2 / CO2e avoided via EPA eGRID 2023 subregion factors (spec Ch 6.5).

ZIP -> eGRID subregion via the bundled Power Profiler crosswalk; falls back to
the U.S. national average output rate (822.4 lb CO2/MWh) when a ZIP is unmapped.
"""
from __future__ import annotations

from . import datastore

NATIONAL_CO2_LB_PER_MWH = 822.4
# Avg U.S. passenger vehicle: 4.6 metric tons CO2/yr = ~10,141 lb/yr (EPA).
LB_CO2_PER_VEHICLE_YEAR = 10141.0
KG_PER_LB = 0.453592


def _factor_for_zip(zip_code: str, co2e: bool = False) -> tuple[float, str]:
    key = "co2e_lb_per_mwh" if co2e else "co2_lb_per_mwh"
    crosswalk = datastore.zip_crosswalk().get(zip_code)
    egrid = datastore.egrid()
    if crosswalk and crosswalk["subregion"] in egrid:
        rec = egrid[crosswalk["subregion"]]
        return rec[key], rec["subregion"]
    nat = egrid.get("NATIONAL")
    if nat:
        return nat[key], "NATIONAL"
    return NATIONAL_CO2_LB_PER_MWH, "NATIONAL"


def lb_co2_avoided(delta_electricity_kwh: float, zip_code: str) -> float:
    """Annual CO2 avoided (lb), eGRID 2023 total output rates."""
    rate_lb_per_mwh, _ = _factor_for_zip(zip_code, co2e=False)
    return (delta_electricity_kwh / 1000.0) * rate_lb_per_mwh


def co2e_kg_avoided(delta_electricity_kwh: float, zip_code: str) -> float:
    """CO2e (kg) including CH4 + N2O at GWP-100 weights."""
    rate_lb_per_mwh, _ = _factor_for_zip(zip_code, co2e=True)
    return (delta_electricity_kwh / 1000.0) * rate_lb_per_mwh * KG_PER_LB


def equivalent_vehicle_years(lb_co2: float) -> float:
    """Passenger-vehicle-years equivalent — a familiar framing for reports."""
    return lb_co2 / LB_CO2_PER_VEHICLE_YEAR


def subregion_for_zip(zip_code: str) -> dict:
    rate, subregion = _factor_for_zip(zip_code)
    rec = datastore.egrid().get(subregion, {})
    return {
        "zip": zip_code,
        "subregion": subregion,
        "subregion_name": rec.get("subregion_name", subregion),
        "co2_lb_per_mwh": rec.get("co2_lb_per_mwh", rate),
        "co2e_lb_per_mwh": rec.get("co2e_lb_per_mwh", rate),
        "source": "EPA eGRID 2023",
    }

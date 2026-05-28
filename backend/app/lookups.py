"""ZIP-driven lookups for project intake auto-fill (spec Ch 10.4).

solar (PVWatts), utility (OpenEI URDB), climate zone, and eGRID subregion. Each
prefers a live upstream call when an API key is set and falls back to bundled
data so intake works offline in the beta."""
from __future__ import annotations

from typing import Any

import httpx

from energy_modeler import carbon, datastore
from energy_modeler.config import settings
from energy_modeler.engine import weather

# Representative commercial $/kWh defaults by eGRID subregion (offline fallback).
DEFAULT_RATE_BY_SUBREGION = {
    "FRCC": 0.1145, "CAMX": 0.1980, "ERCT": 0.0865, "MROW": 0.1050,
    "RMPA": 0.1010, "SRSO": 0.0950, "RFCE": 0.1180, "AZNM": 0.1090,
    "NYCW": 0.2150, "NEWE": 0.1850,
}
DEFAULT_RATE = 0.1150
OPENEI_URL = "https://api.openei.org/utility_rates"


def resolve_zip(zip_code: str) -> dict[str, Any] | None:
    return datastore.get_zip(zip_code)


def climate_zone_for_zip(zip_code: str) -> str | None:
    z = datastore.get_zip(zip_code)
    return z["climate_zone"] if z else None


def egrid_for_zip(zip_code: str) -> dict[str, Any]:
    return carbon.subregion_for_zip(zip_code)


def solar_for_zip(zip_code: str, climate_zone: str | None = None) -> dict[str, Any]:
    return weather.solar_resource(zip_code, climate_zone)


def _live_utility(zip_code: str) -> dict[str, Any] | None:
    if not settings.nrel_api_key:
        return None
    try:
        resp = httpx.get(
            OPENEI_URL,
            params={
                "version": 8, "format": "json", "api_key": settings.nrel_api_key,
                "address": zip_code, "sector": "Commercial", "approved": "true", "limit": 5,
            },
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None
        top = items[0]
        rates = top.get("energyratestructure", [[{"rate": DEFAULT_RATE}]])
        flat = [tier.get("rate", 0) for period in rates for tier in period if tier.get("rate")]
        avg = sum(flat) / len(flat) if flat else DEFAULT_RATE
        return {
            "zip": zip_code,
            "default_utility": top.get("utility"),
            "urdb_label": top.get("label"),
            "rate_name": top.get("name"),
            "avg_energy_rate_usd_kwh": round(avg, 4),
            "has_time_of_use": bool(top.get("energyweekdayschedule")),
            "has_demand_charges": bool(top.get("demandratestructure")),
            "source": "OpenEI URDB v8",
        }
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        return None


def utility_for_zip(zip_code: str) -> dict[str, Any]:
    live = _live_utility(zip_code)
    if live:
        return live
    z = datastore.get_zip(zip_code)
    subregion = z["subregion"] if z else "NATIONAL"
    rate = DEFAULT_RATE_BY_SUBREGION.get(subregion, DEFAULT_RATE)
    return {
        "zip": zip_code,
        "default_utility": None,
        "urdb_label": None,
        "rate_name": "Commercial default (offline)",
        "avg_energy_rate_usd_kwh": rate,
        "has_time_of_use": False,
        "has_demand_charges": False,
        "source": "Bundled default rate (set NREL_API_KEY for live OpenEI URDB)",
    }

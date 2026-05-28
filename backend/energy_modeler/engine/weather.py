"""Weather + solar resource resolution (spec Ch 8.1/8.2).

ZIP -> nearest TMY3 station and monthly plane-of-array (POA) irradiance per
window face. With NREL_API_KEY set this calls NREL PVWatts v8 live; otherwise it
serves representative POA from the bundled climate table so the platform runs
fully offline in the beta. POA drives the pre-flight estimate and the analytical
fallback engine — the production EnergyPlus run uses the TMY3 .epw directly."""
from __future__ import annotations

from typing import Any

import httpx

from .. import datastore
from ..config import settings

PVWATTS_URL = "https://developer.nrel.gov/api/pvwatts/v8.json"

# Window face -> (tilt, azimuth) in PVWatts/EnergyPlus convention
# (azimuth clockwise from north: 0=N, 90=E, 180=S, 270=W; tilt 90 = vertical).
FACE_GEOMETRY = {
    "S": (90.0, 180.0),
    "N": (90.0, 0.0),
    "E": (90.0, 90.0),
    "W": (90.0, 270.0),
    "H": (0.0, 180.0),
}


def _live_poa(lat: float, lon: float, face: str) -> list[float] | None:
    if not settings.nrel_api_key:
        return None
    tilt, azimuth = FACE_GEOMETRY[face]
    try:
        resp = httpx.get(
            PVWATTS_URL,
            params={
                "api_key": settings.nrel_api_key,
                "lat": lat,
                "lon": lon,
                "system_capacity": 1.0,
                "module_type": 0,
                "losses": 0,
                "array_type": 0,
                "tilt": tilt,
                "azimuth": azimuth,
                "dataset": "nsrdb",
                "timeframe": "monthly",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["outputs"]["poa_monthly"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def solar_resource(zip_code: str, climate_zone: str | None = None) -> dict[str, Any]:
    """Return monthly POA per face plus station metadata for a ZIP."""
    z = datastore.get_zip(zip_code)
    cz = climate_zone or (z["climate_zone"] if z else "4A")
    fallback = datastore.get_climate_solar(cz) or {}

    poa: dict[str, list[float]] = {}
    source = "NREL PVWatts v8 / NSRDB"
    used_live = False
    for face in ("S", "E", "W", "N", "H"):
        live = _live_poa(z["lat"], z["lon"], face) if z else None
        if live:
            poa[f"{face}_vertical" if face != "H" else "horizontal"] = live
            used_live = True
        else:
            poa[f"{face}_vertical" if face != "H" else "horizontal"] = fallback.get(face, [])
    if not used_live:
        source = "Bundled climate POA (offline fallback — set NREL_API_KEY for live data)"

    return {
        "zip": zip_code,
        "climate_zone": cz,
        "lat": z["lat"] if z else None,
        "lon": z["lon"] if z else None,
        "station_id": z["station_id"] if z else None,
        "station_city": z["station_city"] if z else None,
        "ghi_kwh_m2_yr": fallback.get("ghi_kwh_m2_yr"),
        "poa_monthly_kwh_m2": poa,
        "source": source,
    }


def monthly_poa_by_face(zip_code: str, climate_zone: str) -> dict[str, list[float]]:
    """{'S': [...12], 'E': [...], 'W': [...], 'N': [...], 'H': [...]} for the engine."""
    fallback = datastore.get_climate_solar(climate_zone) or {}
    z = datastore.get_zip(zip_code)
    out: dict[str, list[float]] = {}
    for face in ("S", "E", "W", "N", "H"):
        live = _live_poa(z["lat"], z["lon"], face) if z else None
        out[face] = live or fallback.get(face, [0.0] * 12)
    return out

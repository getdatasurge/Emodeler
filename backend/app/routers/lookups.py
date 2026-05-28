"""ZIP lookup endpoints (spec Ch 10.4)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import lookups

router = APIRouter(tags=["lookups"])


@router.get("/api/solar/{zip_code}")
def get_solar(zip_code: str):
    return lookups.solar_for_zip(zip_code)


@router.get("/api/utility/{zip_code}")
def get_utility(zip_code: str):
    return lookups.utility_for_zip(zip_code)


@router.get("/api/climate-zone/{zip_code}")
def get_climate_zone(zip_code: str):
    cz = lookups.climate_zone_for_zip(zip_code)
    z = lookups.resolve_zip(zip_code)
    if cz is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "ZIP not in bundled crosswalk", "code": "ZIP_NOT_FOUND",
                    "details": {"zip": zip_code}},
        )
    return {"zip": zip_code, "climate_zone": cz, "lat": z["lat"], "lon": z["lon"],
            "station_id": z["station_id"], "station_city": z["station_city"]}


@router.get("/api/egrid/{zip_code}")
def get_egrid(zip_code: str):
    return lookups.egrid_for_zip(zip_code)

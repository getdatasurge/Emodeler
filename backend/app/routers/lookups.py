"""ZIP lookup endpoints (spec Ch 10.4) with a 30-day cache + X-Cache header."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import cache, lookups
from ..db import get_session

router = APIRouter(tags=["lookups"])


def _climate_zone_payload(zip_code: str) -> dict:
    cz = lookups.climate_zone_for_zip(zip_code)
    z = lookups.resolve_zip(zip_code)
    if cz is None or z is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "ZIP not in bundled crosswalk", "code": "ZIP_NOT_FOUND",
                    "details": {"zip": zip_code}},
        )
    return {"zip": zip_code, "climate_zone": cz, "lat": z["lat"], "lon": z["lon"],
            "station_id": z["station_id"], "station_city": z["station_city"]}


def _cached(response: Response, session: Session, zip_code: str, kind: str, producer):
    payload, hit = cache.get_or_set(session, zip_code, kind, producer)
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return payload


@router.get("/api/solar/{zip_code}")
def get_solar(zip_code: str, response: Response, session: Session = Depends(get_session)):
    return _cached(response, session, zip_code, "solar", lambda: lookups.solar_for_zip(zip_code))


@router.get("/api/utility/{zip_code}")
def get_utility(zip_code: str, response: Response, session: Session = Depends(get_session)):
    return _cached(response, session, zip_code, "utility", lambda: lookups.utility_for_zip(zip_code))


@router.get("/api/climate-zone/{zip_code}")
def get_climate_zone(zip_code: str, response: Response, session: Session = Depends(get_session)):
    return _cached(response, session, zip_code, "climate_zone", lambda: _climate_zone_payload(zip_code))


@router.get("/api/egrid/{zip_code}")
def get_egrid(zip_code: str, response: Response, session: Session = Depends(get_session)):
    return _cached(response, session, zip_code, "egrid", lambda: lookups.egrid_for_zip(zip_code))

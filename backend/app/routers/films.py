"""Film catalog + base glazing endpoints (spec Ch 7, 10.1)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from energy_modeler import datastore
from energy_modeler.engine.film_catalog import resolve as resolve_film
from energy_modeler.engine.glazing import applied_properties

router = APIRouter(tags=["catalog"])


@router.get("/api/films")
def list_films():
    return [
        {k: v for k, v in f.items() if k != "optical"} | {"is_active": True}
        for f in datastore.films()
    ]


@router.get("/api/films/{sku}")
def get_film(sku: str):
    rec = datastore.get_film(sku)
    if rec is None:
        raise HTTPException(status_code=404, detail={"error": "Unknown film SKU",
                            "code": "NOT_FOUND", "details": {"sku": sku}})
    return rec


@router.get("/api/base-glazings")
def list_base_glazings():
    return datastore.base_glazings()


@router.get("/api/films/{sku}/pairings/{base_glazing_id}")
def get_pairing(sku: str, base_glazing_id: str):
    base = datastore.get_base_glazing(base_glazing_id)
    if base is None:
        raise HTTPException(status_code=404, detail={"error": "Unknown base glazing",
                            "code": "NOT_FOUND", "details": {"base_glazing_id": base_glazing_id}})
    try:
        film = resolve_film(sku)
    except KeyError:
        raise HTTPException(status_code=404, detail={"error": "Unknown film SKU",
                            "code": "NOT_FOUND", "details": {"sku": sku}})
    props = applied_properties(base, film)
    return {
        "film_sku": sku,
        "base_glazing_id": base_glazing_id,
        "shgc": props.shgc,
        "u_btu_h_ft2_F": props.u_factor_btuhrft2F,
        "vt": props.vt,
        "base_shgc": base["shgc"],
        "source": "igsdb_scaled",
    }

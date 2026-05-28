"""Loads the bundled reference data (films, base glazings, eGRID, prototypes,
ZIP crosswalk, climate solar) and exposes typed lookups. Cached at import."""
from __future__ import annotations

import csv
import json
from functools import lru_cache
from typing import Any

from .config import DATA_DIR


@lru_cache(maxsize=1)
def films() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "films.json").read_text())


@lru_cache(maxsize=1)
def _films_by_sku() -> dict[str, dict[str, Any]]:
    return {f["sku"]: f for f in films()}


def get_film(sku: str) -> dict[str, Any] | None:
    return _films_by_sku().get(sku)


@lru_cache(maxsize=1)
def base_glazings() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "base_glazings.json").read_text())


@lru_cache(maxsize=1)
def _glazings_by_id() -> dict[str, dict[str, Any]]:
    return {g["id"]: g for g in base_glazings()}


def get_base_glazing(glazing_id: str) -> dict[str, Any] | None:
    return _glazings_by_id().get(glazing_id)


@lru_cache(maxsize=1)
def prototypes() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "prototypes.json").read_text())["prototypes"]


@lru_cache(maxsize=1)
def _prototypes_by_id() -> dict[str, dict[str, Any]]:
    return {p["id"]: p for p in prototypes()}


def get_prototype(building_type: str) -> dict[str, Any] | None:
    return _prototypes_by_id().get(building_type)


@lru_cache(maxsize=1)
def egrid() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with (DATA_DIR / "egrid_2023.csv").open() as fh:
        for row in csv.DictReader(fh):
            out[row["subregion"]] = {
                "subregion": row["subregion"],
                "subregion_name": row["subregion_name"],
                "co2_lb_per_mwh": float(row["co2_lb_per_mwh"]),
                "co2e_lb_per_mwh": float(row["co2e_lb_per_mwh"]),
                "source": row["source"],
            }
    return out


@lru_cache(maxsize=1)
def zip_crosswalk() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with (DATA_DIR / "zip_crosswalk.csv").open() as fh:
        for row in csv.DictReader(fh):
            out[row["zip"]] = {
                "zip": row["zip"],
                "subregion": row["subregion"],
                "climate_zone": row["climate_zone"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "station_id": row["station_id"],
                "station_city": row["station_city"],
            }
    return out


def get_zip(zip_code: str) -> dict[str, Any] | None:
    return zip_crosswalk().get(zip_code)


@lru_cache(maxsize=1)
def climate_solar() -> dict[str, Any]:
    return json.loads((DATA_DIR / "climate_solar.json").read_text())["zones"]


def get_climate_solar(climate_zone: str) -> dict[str, Any] | None:
    zones = climate_solar()
    if climate_zone in zones:
        return zones[climate_zone]
    # Fall back to the same numeric zone (e.g. '5C' -> '5B' -> any '5x').
    prefix = climate_zone[:1]
    for code, data in zones.items():
        if code.startswith(prefix):
            return data
    return zones.get("4A")

"""DOE Commercial Prototype Building loading + scaling (spec Ch 5.3).

Production: resolve (building_type, climate_zone, standard) -> bundled IDF under
PROTOTYPES_DIR, load via eppy, scale geometry to the project floor area, and map
measured per-orientation glazing onto the window surfaces.

Beta: when eppy / the prototype IDFs are absent we return the prototype's
aggregate metadata plus a floor-area scale factor, which is what the analytical
fallback engine consumes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import datastore


@dataclass
class LoadedPrototype:
    building_type: str
    climate_zone: str
    nominal_area_sf: float
    target_area_sf: float
    scale_factor: float
    meta: dict[str, Any]
    idf_path: str | None = None  # set when a real prototype IDF is loaded


def load(building_type: str, climate_zone: str, target_area_sf: float) -> LoadedPrototype:
    meta = datastore.get_prototype(building_type)
    if meta is None:
        raise KeyError(f"Unknown prototype building_type: {building_type!r}")
    nominal = float(meta["nominal_area_sf"])
    target = float(target_area_sf) if target_area_sf else nominal
    scale = target / nominal if nominal else 1.0
    return LoadedPrototype(
        building_type=building_type,
        climate_zone=climate_zone,
        nominal_area_sf=nominal,
        target_area_sf=target,
        scale_factor=round(scale, 4),
        meta=meta,
    )

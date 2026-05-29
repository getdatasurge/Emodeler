"""DOE Commercial Prototype Building loading + scaling (spec Ch 5.3).

Production: resolve (building_type, climate_zone, standard) -> bundled IDF under
PROTOTYPES_DIR, load via eppy, scale geometry to the project floor area, and map
measured per-orientation glazing onto the window surfaces.

Beta: when eppy / the prototype IDFs are absent we return the prototype's
aggregate metadata plus a floor-area scale factor, which is what the analytical
fallback engine consumes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import datastore
from ..config import DATA_DIR, settings


class PrototypeNotFound(Exception):
    """Raised when the bundled prototype IDF or the EnergyPlus IDD is absent —
    the runner catches this and falls back to the labeled analytical estimate."""


def _idd_path() -> str | None:
    if settings.energyplus_dir:
        cand = Path(settings.energyplus_dir) / "Energy+.idd"
        if cand.exists():
            return str(cand)
    return None


def _find_prototype_idf(building_type: str, climate_zone: str, standard: str) -> Path | None:
    from .building import city_for_zone

    root = Path(settings.prototypes_dir) if settings.prototypes_dir else DATA_DIR / "prototypes"
    base = root / standard / building_type
    if not base.exists():
        return None
    # DOE prototype IDFs are named by representative city (e.g. ..._Tampa.idf).
    city = city_for_zone(climate_zone)
    if city:
        for idf in base.glob(f"*_{city}.idf"):
            return idf
    idfs = sorted(base.glob("*.idf"))
    return idfs[0] if idfs else None


def load_idf(building_type: str, climate_zone: str, standard: str = "ASHRAE901_2019"):
    """Load the DOE prototype IDF via eppy. Raises PrototypeNotFound when the
    bundled IDF or the EnergyPlus IDD is unavailable (the beta path)."""
    try:
        from eppy.modeleditor import IDF
    except ImportError as exc:
        raise PrototypeNotFound("eppy not installed (worker-image dependency)") from exc
    idd = _idd_path()
    if idd is None:
        raise PrototypeNotFound("EnergyPlus IDD not found (set ENERGYPLUS_DIR)")
    idf_path = _find_prototype_idf(building_type, climate_zone, standard)
    if idf_path is None:
        raise PrototypeNotFound(
            f"No bundled prototype IDF for {building_type}/{climate_zone} under {standard}"
        )
    try:
        IDF.setiddname(idd)
    except Exception:
        pass  # IDD already set for this process
    return IDF(str(idf_path))


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

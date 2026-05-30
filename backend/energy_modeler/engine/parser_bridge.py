"""Real EnergyPlus pipeline (spec Ch 5.2 / 7.7).

Loads the DOE prototype, builds baseline + film scenario IDFs, runs the
EnergyPlus binary, and parses the outputs into RunResults. runner.run_project
calls this when the binary is configured; it raises PrototypeNotFound (which the
runner catches and degrades to the labeled analytical estimate) whenever the
prototypes / IDD / weather aren't available — i.e. everywhere but a provisioned
worker image."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .. import datastore
from ..parser import results
from ..schemas import RunResult
from . import building, idf_builder, prototype_loader, runner, weather
from .film_catalog import resolve as resolve_film
from .inputs import EngineProject

# Intercardinal -> the two adjacent cardinals each contributes half-area to,
# matching how a SW window catches both the south + west exposure profiles.
_INTERCARDINAL_SPLIT = {"NE": ("N", "E"), "SE": ("S", "E"),
                        "SW": ("S", "W"), "NW": ("N", "W")}

# Fields on EnergyEndUses that represent annual energy in kWh. Scaling them
# uniformly preserves the savings-percentage (what a reviewer focuses on) while
# the absolutes track the project's floor area instead of the prototype's.
_SCALED_ENERGY_FIELDS = (
    "heating_elec_kwh", "heating_gas_kwh", "cooling_elec_kwh",
    "interior_lighting_kwh", "interior_equipment_kwh",
    "fans_kwh", "pumps_kwh", "heat_rejection_kwh",
    "total_electricity_kwh", "total_gas_kwh",
)


def _scale_factor(project: EngineProject, meta: dict[str, Any]) -> tuple[float, float, float]:
    """Prototype-to-project floor-area scaling factor.

    DOE prototypes run at their nominal floor area (~53k sf for MediumOffice)
    regardless of the project's size. Without this rescale the EnergyPlus run
    would report the *prototype's* energy and savings, not the project's — a
    reviewer would catch that immediately on a renovation that's a fraction of
    the prototype. EFILM applies the same scale; we expose it explicitly so the
    audit bundle records the math.

    Returns (factor, project_sf, prototype_sf). factor=1.0 when either side
    is missing.
    """
    proto_sf = float(meta.get("nominal_area_sf") or 0.0)
    project_sf = float(project.gross_floor_area_sf or 0.0)
    if proto_sf <= 0.0 or project_sf <= 0.0:
        return 1.0, project_sf, proto_sf
    return project_sf / proto_sf, project_sf, proto_sf


def _scale_run(rr: RunResult, factor: float) -> None:
    """Scale a parsed RunResult's annual energies + peak demand in place."""
    if factor == 1.0:
        return
    eu = rr.annual_end_uses
    for f in _SCALED_ENERGY_FIELDS:
        setattr(eu, f, round(getattr(eu, f, 0.0) * factor, 1))
    rr.peak_demand.cooling_peak_kw = round(rr.peak_demand.cooling_peak_kw * factor, 2)
    rr.peak_demand.total_facility_peak_kw = round(
        rr.peak_demand.total_facility_peak_kw * factor, 2
    )
    if rr.monthly_cooling_kwh:
        rr.monthly_cooling_kwh = [round(v * factor, 1) for v in rr.monthly_cooling_kwh]


def _glazings_by_cardinal(project: EngineProject) -> dict[str, Any]:
    """Resolve user faces -> per-cardinal base-glazing records for the IDF
    mutator. Each intercardinal contributes half its area to each adjacent
    cardinal; the glazing-id with the most area-weighted votes per cardinal
    wins. Cardinals with no votes inherit the overall-dominant glazing.

    Always returns a 'DEFAULT' entry as the fallback for windows whose
    elevation token can't be parsed from the prototype Name."""
    votes: dict[str, dict[str, float]] = {c: defaultdict(float) for c in ("N", "E", "S", "W")}
    overall: dict[str, float] = defaultdict(float)
    for f in project.faces:
        overall[f.base_glazing_id] += f.area_sqft
        if f.orientation in _INTERCARDINAL_SPLIT:
            for c in _INTERCARDINAL_SPLIT[f.orientation]:
                votes[c][f.base_glazing_id] += f.area_sqft / 2
        elif f.orientation in ("N", "E", "S", "W"):
            votes[f.orientation][f.base_glazing_id] += f.area_sqft

    fallback_id = (max(overall.items(), key=lambda kv: kv[1])[0]
                   if overall else "dbl_clear_3mm_13mmAir")
    fallback_bg = datastore.get_base_glazing(fallback_id) or {}

    out: dict[str, Any] = {}
    for cardinal, glazings in votes.items():
        chosen_id = (max(glazings.items(), key=lambda kv: kv[1])[0]
                     if glazings else fallback_id)
        bg = datastore.get_base_glazing(chosen_id) or fallback_bg
        if bg:
            out[cardinal] = bg
    if fallback_bg:
        out["DEFAULT"] = fallback_bg
    return out


def run_real_pipeline(project: EngineProject) -> tuple[str, RunResult, list[RunResult]]:
    meta = datastore.get_prototype(project.building_type)
    if meta is None:
        raise prototype_loader.PrototypeNotFound(f"Unknown building_type {project.building_type!r}")
    bldg = building.resolve(project, meta)
    # Per-cardinal base glazing — preserves mixed-glass buildings instead of
    # collapsing the whole envelope to face[0]'s glazing.
    base_glazing = _glazings_by_cardinal(project)

    # Fail fast (and cleanly) when the prototype IDF / IDD aren't bundled.
    prototype_loader.load_idf(project.building_type, project.climate_zone)
    epw = weather.epw_for_zip(project.zip)
    z = datastore.get_zip(project.zip)
    station = z["station_city"] if z else "EnergyPlus run"

    scenarios: list[tuple[str, object | None]] = [("baseline", None)]
    scenarios += [(s.label, resolve_film(s.film_sku)) for s in project.scenarios]

    baseline: RunResult | None = None
    film_runs: list[RunResult] = []
    with TemporaryDirectory() as tmp:
        for label, film in scenarios:
            idf = prototype_loader.load_idf(project.building_type, project.climate_zone)
            idf_builder.build_scenario_idf(idf, base_glazing, film, bldg, label)
            scen_dir = Path(tmp) / label.replace(" ", "_")
            scen_dir.mkdir(parents=True, exist_ok=True)
            idf_path = scen_dir / f"{label.replace(' ', '_')}.idf"
            idf.saveas(str(idf_path))
            runner.run_energyplus(idf_path, Path(epw), scen_dir)
            rr = results.parse_run(scen_dir / idf_path.stem, label, station=station)
            if film is None:
                baseline = rr
            else:
                film_runs.append(rr)

    assert baseline is not None
    scale, project_sf, proto_sf = _scale_factor(project, meta)
    if scale != 1.0:
        for rr in [baseline, *film_runs]:
            _scale_run(rr, scale)
            rr.warnings.append(
                f"Prototype-to-project scale factor: {scale:.4f} "
                f"({project_sf:.0f} sf project / {proto_sf:.0f} sf prototype) "
                "applied uniformly to end-uses + peak demand."
            )
    return "energyplus", baseline, film_runs

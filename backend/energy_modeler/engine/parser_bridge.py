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
from ..parser.eplus_window_solar import parse_window_transmitted_solar
from ..schemas import RunResult, WindowSurfaceResult
from . import building, idf_builder, prototype_loader, runner, weather
from .film_catalog import resolve as resolve_film
from .idf_ops import _cardinal_from_window_name
from .inputs import EngineProject

# Same azimuths the FACE_GEOMETRY table uses (0=N, 90=E, 180=S, 270=W). We
# stamp one per orientation onto the aggregated WindowSurfaceResult so the
# audit bundle records what the chart's bars represent.
_CARDINAL_AZIMUTH = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}

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


def _prototype_glazing_sf(meta: dict[str, Any]) -> float:
    """Estimate the DOE prototype's exterior glazing area from its meta
    (nominal_area_sf, floors, wwr). Matches engine.building.resolve's
    square-footprint assumption so the two paths stay consistent."""
    import math as _math

    proto_sf = float(meta.get("nominal_area_sf") or 0.0)
    floors = max(int(meta.get("floors") or 1), 1)
    wwr = float(meta.get("wwr") or 0.0)
    if proto_sf <= 0.0 or wwr <= 0.0:
        return 0.0
    footprint = proto_sf / floors
    perimeter_ft = 4.0 * _math.sqrt(footprint)
    floor_to_floor = 13.0  # matches building.DEFAULT_FLOOR_TO_FLOOR_FT
    return perimeter_ft * floor_to_floor * floors * wwr


def _scale_factors(project: EngineProject, meta: dict[str, Any]) -> dict[str, float]:
    """Compute both candidate scale factors so the run records the math
    regardless of which one was applied.

    floor:    project_floor_sf / prototype_floor_sf — matches EFILM.
    glazing:  sum(face.area_sqft) / prototype_glazing_sf — more physical for
              window-film savings since the savings delta is glazing-area-driven.
    """
    project_sf = float(project.gross_floor_area_sf or 0.0)
    proto_sf = float(meta.get("nominal_area_sf") or 0.0)
    project_glazing = sum((f.area_sqft or 0.0) for f in project.faces)
    proto_glazing = _prototype_glazing_sf(meta)
    floor = project_sf / proto_sf if (proto_sf > 0 and project_sf > 0) else 1.0
    glazing = (
        project_glazing / proto_glazing
        if (proto_glazing > 0 and project_glazing > 0)
        else 1.0
    )
    return {
        "floor": floor,
        "glazing": glazing,
        "project_floor_sf": project_sf,
        "proto_floor_sf": proto_sf,
        "project_glazing_sf": project_glazing,
        "proto_glazing_sf": round(proto_glazing, 1),
    }


# Backward-compat alias for callers (incl. tests) that still expect the older
# floor-only signature: (factor, project_sf, proto_sf).
def _scale_factor(
    project: EngineProject, meta: dict[str, Any]
) -> tuple[float, float, float]:
    f = _scale_factors(project, meta)
    return f["floor"], f["project_floor_sf"], f["proto_floor_sf"]


def _attach_window_solar(rr: RunResult, run_dir, scale: float) -> None:
    """Aggregate per-window transmitted solar by cardinal direction (parsed
    from the prototype window Name) and stamp one WindowSurfaceResult per
    orientation onto the RunResult so the 'Solar gain rejected by face' chart
    has data. Quietly leaves windows=[] when the variable isn't in the CSV
    (e.g. older runs without our outputs block)."""
    per_window = parse_window_transmitted_solar(run_dir)
    if not per_window:
        return
    per_orient: dict[str, float] = {}
    for window_name, kwh in per_window.items():
        cardinal = _cardinal_from_window_name(window_name) or "?"
        per_orient[cardinal] = per_orient.get(cardinal, 0.0) + kwh
    surfaces: list[WindowSurfaceResult] = []
    # Stable order — matches the chart's preferred ordering.
    for cardinal in ("S", "E", "W", "N", "NE", "SE", "SW", "NW", "H", "?"):
        if cardinal not in per_orient:
            continue
        annual_kwh = per_orient[cardinal] * scale
        surfaces.append(
            WindowSurfaceResult(
                surface_name=f"Face_{cardinal}_total",
                orientation_deg=_CARDINAL_AZIMUTH.get(cardinal, -1.0),
                tilt_deg=0.0 if cardinal == "H" else 90.0,
                area_m2=0.0,  # aggregate row, not a single surface area
                annual_solar_transmitted_kwh=round(annual_kwh, 1),
            )
        )
    rr.windows = surfaces


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
    # Per-orientation transmitted solar (attached by _attach_window_solar)
    # also scales — it's a glazing-area-driven aggregate.
    for w in rr.windows:
        w.annual_solar_transmitted_kwh = round(
            w.annual_solar_transmitted_kwh * factor, 1
        )


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


def run_real_pipeline(
    project: EngineProject,
) -> tuple[str, RunResult, list[RunResult], RunResult | None]:
    """Run the real EnergyPlus pipeline. Returns (engine_mode, baseline_run,
    film_runs, appendix_g_run). The 4th element is the ASHRAE 90.1-2019
    Appendix G baseline run when CalcOptions.include_appendix_g_baseline=true,
    else None — LEED EAc PCI compares the project against this anchor."""
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
    appendix_g_run: RunResult | None = None
    with TemporaryDirectory() as tmp:
        for label, film in scenarios:
            idf = prototype_loader.load_idf(project.building_type, project.climate_zone)
            idf_builder.build_scenario_idf(idf, base_glazing, film, bldg, label)
            if project.options.add_daylighting_controls:
                from . import idf_ops as _idf_ops
                _idf_ops.add_daylighting_controls(idf)
            scen_dir = Path(tmp) / label.replace(" ", "_")
            scen_dir.mkdir(parents=True, exist_ok=True)
            idf_path = scen_dir / f"{label.replace(' ', '_')}.idf"
            idf.saveas(str(idf_path))
            runner.run_energyplus(idf_path, Path(epw), scen_dir)
            run_output_dir = scen_dir / idf_path.stem
            rr = results.parse_run(run_output_dir, label, station=station)
            # Per-orientation transmitted solar BEFORE we apply the floor-area
            # scale below — pass scale=1.0 so the aggregator returns the raw
            # parsed values; the post-loop _scale_run still multiplies them.
            _attach_window_solar(rr, run_output_dir, scale=1.0)
            if film is None:
                baseline = rr
            else:
                film_runs.append(rr)

        # ASHRAE 90.1-2019 Appendix G baseline (LEED PCI anchor). One extra
        # run with the prescriptive SimpleGlazing per the climate zone +
        # baseline LPD per the building type.
        if project.options.include_appendix_g_baseline:
            from . import appendix_g

            spec = appendix_g.baseline_spec(
                project.building_type, project.climate_zone,
                bldg.num_floors, project.gross_floor_area_sf,
            )
            idf = prototype_loader.load_idf(project.building_type, project.climate_zone)
            appendix_g.build_baseline_idf(idf, spec)
            scen_dir = Path(tmp) / "appG_baseline"
            scen_dir.mkdir(parents=True, exist_ok=True)
            idf_path = scen_dir / "appG_baseline.idf"
            idf.saveas(str(idf_path))
            runner.run_energyplus(idf_path, Path(epw), scen_dir)
            run_output_dir = scen_dir / idf_path.stem
            appendix_g_run = results.parse_run(
                run_output_dir, "ASHRAE 90.1-2019 Appendix G", station=station,
            )
            _attach_window_solar(appendix_g_run, run_output_dir, scale=1.0)

    assert baseline is not None
    factors = _scale_factors(project, meta)
    basis = (project.options.scaling_basis or "floor").lower()
    applied = factors.get(basis, factors["floor"])
    if applied != 1.0:
        runs_to_scale = [baseline, *film_runs]
        if appendix_g_run is not None:
            runs_to_scale.append(appendix_g_run)
        for rr in runs_to_scale:
            _scale_run(rr, applied)
            rr.warnings.append(
                f"Prototype-to-project scale: basis={basis} factor={applied:.4f} "
                f"(floor {factors['floor']:.4f} = "
                f"{factors['project_floor_sf']:.0f}/{factors['proto_floor_sf']:.0f} sf, "
                f"glazing {factors['glazing']:.4f} = "
                f"{factors['project_glazing_sf']:.0f}/{factors['proto_glazing_sf']:.0f} sf). "
                "Applied uniformly to end-uses + peak demand + transmitted solar."
            )
    return "energyplus", baseline, film_runs, appendix_g_run

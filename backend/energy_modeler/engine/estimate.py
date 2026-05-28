"""Analytical fallback engine.

IMPORTANT — this is NOT EnergyPlus. It is a transparent, physics-lite estimator
used only when the EnergyPlus binary is unavailable (e.g. local dev, CI, or a
demo container). Per spec Ch 2.1, a single-SHGC analytical calculation is NOT an
acceptable methodology for a customer-facing bid deliverable. Every RunResult it
produces is stamped engine_mode='analytical_estimate' and carries a prominent
warning so it can never be mistaken for an audited EnergyPlus result.

Method: per window face and month, the reduction in transmitted solar energy is
POA x area x (SHGC_base - SHGC_film_applied). A per-climate-zone seasonal mask
splits that between cooling savings (divided by system COP -> electricity) and a
heating penalty. Absolute baseline end-uses come from the DOE prototype EUI."""
from __future__ import annotations

import uuid

from .. import datastore
from ..schemas import EnergyEndUses, PeakDemand, RunResult, WindowSurfaceResult
from . import glazing, weather
from .film_catalog import resolve as resolve_film
from .inputs import EngineProject
from .weather import FACE_GEOMETRY

SF_TO_M2 = 0.092903

# Effective cooling COP for converting a window solar-load change to cooling
# electricity. 3.0 is the spec glossary default for packaged commercial cooling
# (Ch 12.3). Fraction of window solar gain that lands as cooling load during the
# cooling season (pickup), and the heating-season counterparts.
EFFECTIVE_COOLING_COP = 3.0
COOLING_PICKUP = 0.95
# Heating penalty is intentionally modest: only a fraction of lost winter solar
# gain raises heating energy (short days, low sun, occupied-hour internal gains,
# and much commercial heating is gas rather than electric).
HEATING_PICKUP = 0.30
HEATING_COP = 3.0
# Share of the prototype's average cooling that is NOT window-solar driven
# (internal loads, ventilation, envelope conduction). The window-solar portion
# is recomputed from the project's actual glazing for self-consistency.
NONWINDOW_COOLING_FRACTION = 0.5

# Per-climate-zone (by leading digit) monthly cooling weights. Heating weight is
# the complement. Hot zones cool nearly year-round; cold zones concentrate
# cooling in summer and incur a winter heating penalty when solar gain is cut.
COOLING_WEIGHTS = {
    "1": [0.85, 0.88, 0.92, 0.96, 1.0, 1.0, 1.0, 1.0, 1.0, 0.96, 0.90, 0.85],
    "2": [0.75, 0.80, 0.88, 0.95, 1.0, 1.0, 1.0, 1.0, 0.98, 0.92, 0.82, 0.74],
    "3": [0.60, 0.68, 0.80, 0.90, 0.98, 1.0, 1.0, 1.0, 0.95, 0.85, 0.70, 0.60],
    "4": [0.35, 0.42, 0.58, 0.74, 0.90, 1.0, 1.0, 0.98, 0.82, 0.62, 0.42, 0.34],
    "5": [0.20, 0.26, 0.42, 0.62, 0.82, 0.96, 1.0, 0.96, 0.74, 0.50, 0.28, 0.18],
    "6": [0.10, 0.14, 0.28, 0.48, 0.72, 0.92, 1.0, 0.92, 0.62, 0.36, 0.16, 0.08],
    "7": [0.05, 0.08, 0.18, 0.36, 0.60, 0.84, 0.96, 0.84, 0.50, 0.24, 0.10, 0.04],
    "8": [0.02, 0.04, 0.10, 0.24, 0.46, 0.72, 0.88, 0.72, 0.38, 0.16, 0.05, 0.02],
}

ESTIMATE_WARNING = (
    "PRELIMINARY ESTIMATE — produced by the analytical fallback engine, not "
    "EnergyPlus. Not valid for bid submission, utility rebate filing, or LEED. "
    "Install the EnergyPlus 24.x binary (set ENERGYPLUS_DIR) for audited results."
)

COOLING_HOURS_TO_PEAK_KW = 1800.0  # equivalent full-load cooling hours/yr


def _cooling_weights(climate_zone: str) -> list[float]:
    return COOLING_WEIGHTS.get(climate_zone[:1], COOLING_WEIGHTS["4"])


def _baseline_end_uses(meta: dict, area_sf: float) -> EnergyEndUses:
    total = area_sf * float(meta["nominal_eui_kwh_sf"])
    return EnergyEndUses(
        heating_elec_kwh=round(total * meta["heating_fraction"], 1),
        cooling_elec_kwh=round(total * meta["cooling_fraction"], 1),
        interior_lighting_kwh=round(total * meta["lighting_fraction"], 1),
        fans_kwh=round(total * meta["fan_fraction"], 1),
        interior_equipment_kwh=round(
            total
            * max(
                0.0,
                1.0
                - meta["heating_fraction"]
                - meta["cooling_fraction"]
                - meta["lighting_fraction"]
                - meta["fan_fraction"],
            ),
            1,
        ),
        total_electricity_kwh=round(total, 1),
        total_gas_kwh=0.0,
    )


def _window_results(project: EngineProject, shgc_provider) -> list[WindowSurfaceResult]:
    """shgc_provider(base_glazing_dict) -> shgc to use for the face."""
    poa = weather.monthly_poa_by_face(project.zip, project.climate_zone)
    out: list[WindowSurfaceResult] = []
    for i, face in enumerate(project.faces):
        base = datastore.get_base_glazing(face.base_glazing_id)
        if base is None:
            continue
        area_m2 = face.area_sqft * SF_TO_M2
        annual_poa = sum(poa.get(face.orientation, [0.0] * 12))
        shgc = shgc_provider(base)
        transmitted = annual_poa * area_m2 * shgc
        tilt, azimuth = FACE_GEOMETRY.get(face.orientation, (90.0, 180.0))
        out.append(
            WindowSurfaceResult(
                surface_name=f"Face_{face.orientation}_{i+1}",
                orientation_deg=azimuth,
                tilt_deg=tilt,
                area_m2=round(area_m2, 2),
                annual_solar_transmitted_kwh=round(transmitted, 1),
                annual_heat_gain_kwh=round(transmitted, 1),
                annual_heat_loss_kwh=0.0,
                peak_heat_gain_rate_w=round(area_m2 * shgc * 700.0, 1),
            )
        )
    return out


def _window_solar_loads(project: EngineProject, shgc_provider) -> tuple[float, float]:
    """Window solar load split for a given SHGC choice.

    Returns (cooling_season_thermal_kwh, heating_season_thermal_kwh): the solar
    energy transmitted through all faces, weighted by the per-zone seasonal mask.
    Computing this for both the base SHGC and the film-applied SHGC keeps the
    baseline and film runs self-consistent regardless of how heavily glazed the
    building is."""
    poa = weather.monthly_poa_by_face(project.zip, project.climate_zone)
    weights = _cooling_weights(project.climate_zone)
    cooling_thermal = 0.0
    heating_thermal = 0.0
    for face in project.faces:
        base = datastore.get_base_glazing(face.base_glazing_id)
        if base is None:
            continue
        area_m2 = face.area_sqft * SF_TO_M2
        shgc = shgc_provider(base)
        months = poa.get(face.orientation, [0.0] * 12)
        for m, p in enumerate(months[:12]):
            transmitted = p * area_m2 * shgc
            cooling_thermal += transmitted * weights[m]
            heating_thermal += transmitted * max(0.0, 1.0 - weights[m])
    return cooling_thermal, heating_thermal


def _cooling_elec(window_cooling_thermal: float) -> float:
    return window_cooling_thermal * COOLING_PICKUP / EFFECTIVE_COOLING_COP


def _make_run(
    label: str, end_uses: EnergyEndUses, station: str, windows: list[WindowSurfaceResult]
) -> RunResult:
    return RunResult(
        run_id=str(uuid.uuid4()),
        scenario_label=label,
        engine_mode="analytical_estimate",
        energyplus_version="n/a (analytical estimate)",
        weather_station=station,
        weather_dataset="Bundled climate POA",
        annual_end_uses=end_uses,
        peak_demand=PeakDemand(
            total_facility_peak_kw=round(end_uses.total_electricity_kwh / 2600.0, 2),
            cooling_peak_kw=round(end_uses.cooling_elec_kwh / COOLING_HOURS_TO_PEAK_KW, 2),
        ),
        windows=windows,
        warnings=[ESTIMATE_WARNING],
    )


def run_project(project: EngineProject) -> tuple[RunResult, list[RunResult]]:
    """Produce a baseline RunResult and one per candidate film (estimate mode)."""
    meta = datastore.get_prototype(project.building_type)
    if meta is None:
        raise KeyError(f"Unknown building_type: {project.building_type!r}")
    z = datastore.get_zip(project.zip)
    station = z["station_city"] if z else "Unknown"

    proto = _baseline_end_uses(meta, project.gross_floor_area_sf)
    # Split the prototype's cooling into a non-window portion (kept fixed) and a
    # window-solar portion (recomputed from the project's actual glazing).
    nonwindow_cooling = proto.cooling_elec_kwh * NONWINDOW_COOLING_FRACTION

    def base_shgc(base):
        return float(base["shgc"])

    base_cool_thermal, _ = _window_solar_loads(project, base_shgc)
    baseline_window_cooling = _cooling_elec(base_cool_thermal)

    base_uses = EnergyEndUses(
        heating_elec_kwh=proto.heating_elec_kwh,
        cooling_elec_kwh=round(nonwindow_cooling + baseline_window_cooling, 1),
        interior_lighting_kwh=proto.interior_lighting_kwh,
        interior_equipment_kwh=proto.interior_equipment_kwh,
        fans_kwh=proto.fans_kwh,
        total_electricity_kwh=round(
            proto.total_electricity_kwh
            - proto.cooling_elec_kwh
            + nonwindow_cooling
            + baseline_window_cooling,
            1,
        ),
        total_gas_kwh=0.0,
    )
    baseline = _make_run("baseline", base_uses, station, _window_results(project, base_shgc))

    film_runs: list[RunResult] = []
    for scenario in project.scenarios:
        film = resolve_film(scenario.film_sku)

        def applied_shgc(base, _film=film):
            return glazing.applied_properties(base, _film).shgc

        film_cool_thermal, film_heat_thermal = _window_solar_loads(project, applied_shgc)
        _, base_heat_thermal = _window_solar_loads(project, base_shgc)
        film_window_cooling = _cooling_elec(film_cool_thermal)
        # Lost beneficial winter solar gain becomes a heating penalty.
        heating_penalty = max(0.0, base_heat_thermal - film_heat_thermal) * HEATING_PICKUP / HEATING_COP

        film_cooling = nonwindow_cooling + film_window_cooling
        film_heating = proto.heating_elec_kwh + heating_penalty
        film_uses = EnergyEndUses(
            heating_elec_kwh=round(film_heating, 1),
            cooling_elec_kwh=round(film_cooling, 1),
            interior_lighting_kwh=proto.interior_lighting_kwh,
            interior_equipment_kwh=proto.interior_equipment_kwh,
            fans_kwh=proto.fans_kwh,
            total_electricity_kwh=round(
                proto.total_electricity_kwh
                - proto.cooling_elec_kwh
                + film_cooling
                + heating_penalty,
                1,
            ),
            total_gas_kwh=0.0,
        )
        film_runs.append(
            _make_run(scenario.label, film_uses, station, _window_results(project, applied_shgc))
        )
    return baseline, film_runs

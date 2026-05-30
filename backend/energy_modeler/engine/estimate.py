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
from . import building, glazing, weather
from .film_catalog import resolve as resolve_film
from .inputs import EngineProject
from .weather import FACE_GEOMETRY

SF_TO_M2 = 0.092903

# Cooling and heating COP are resolved per-project (engine.building), defaulting
# to the DOE prototype `cop`. The pickups are the fraction of the window
# solar-load change that lands as cooling load in the cooling season, and the
# smaller fraction of lost winter solar that raises heating energy (short days,
# low sun, internal gains, and much commercial heating is gas not electric).
COOLING_PICKUP = 0.95
HEATING_PICKUP = 0.30
# Rated COP overstates real performance: seasonal/part-load operation (the basis
# of SEER/IEER) runs lower. Derate the rated COP when converting cooling load to
# electricity so the estimate isn't optimistic about system efficiency.
SEASONAL_COP_DERATE = 0.85
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
    "Install the EnergyPlus 22.1 binary (matches the bundled DOE prototypes) for audited results."
)

COOLING_HOURS_TO_PEAK_KW = 1800.0  # equivalent full-load cooling hours/yr

# Daylight-harvesting penalty: cutting visible transmittance makes daylight-
# controlled zones run electric lighting more (delta_lighting was always 0).
# Fraction of a building type's lighting energy in daylit (perimeter) zones:
DAYLIT_FRACTION = {
    "SmallOffice": 0.30, "MediumOffice": 0.30, "LargeOffice": 0.35,
    "PrimarySchool": 0.30, "SecondarySchool": 0.30,
    "StandaloneRetail": 0.20, "StripMall": 0.15, "Warehouse": 0.10,
}
DAYLIGHT_CONTROL_EFFECTIVENESS = 0.5  # continuous dimming captures ~half the theoretical


def _cooling_weights(climate_zone: str) -> list[float]:
    return COOLING_WEIGHTS.get(climate_zone[:1], COOLING_WEIGHTS["4"])


def _avg_vt(project: EngineProject, props_provider) -> float:
    """Area-weighted visible transmittance across the project's glazed faces."""
    total_area = vt_area = 0.0
    for face in project.faces:
        base = datastore.get_base_glazing(face.base_glazing_id)
        if base is None:
            continue
        total_area += face.area_sqft
        vt_area += props_provider(base).vt * face.area_sqft
    return vt_area / total_area if total_area else 0.0


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


def _window_results(
    project: EngineProject, props_provider, bldg: building.ResolvedBuilding
) -> list[WindowSurfaceResult]:
    """props_provider(base_glazing_dict) -> GlazingProperties (shgc + U) for the face.

    Heat gain = transmitted solar + summer conduction (U.A.CDD); heat loss =
    winter conduction (U.A.HDD). Peak gain uses an orientation-specific design
    irradiance (west highest, north lowest), not a single flat value."""
    poa = weather.monthly_poa_by_face(project.zip, project.climate_zone)
    out: list[WindowSurfaceResult] = []
    for i, face in enumerate(project.faces):
        base = datastore.get_base_glazing(face.base_glazing_id)
        if base is None:
            continue
        area_m2 = face.area_sqft * SF_TO_M2
        annual_poa = sum(poa.get(face.orientation, [0.0] * 12))
        props = props_provider(base)
        shgc = props.shgc
        transmitted = annual_poa * area_m2 * shgc
        cond_loss = building.conduction_kwh(props.u_factor_btuhrft2F, face.area_sqft, bldg.hdd65)
        cond_gain = building.conduction_kwh(props.u_factor_btuhrft2F, face.area_sqft, bldg.cdd65)
        default_tilt, azimuth = FACE_GEOMETRY.get(face.orientation, (90.0, 180.0))
        # User-supplied per-face tilt wins; otherwise vertical (or horizontal
        # for H) per the orientation's default. Captured in the audit so a
        # sloped-glass project isn't misreported as vertical.
        tilt = float(face.tilt_deg) if face.tilt_deg is not None else default_tilt
        out.append(
            WindowSurfaceResult(
                surface_name=f"Face_{face.orientation}_{i+1}",
                orientation_deg=azimuth,
                tilt_deg=tilt,
                area_m2=round(area_m2, 2),
                annual_solar_transmitted_kwh=round(transmitted, 1),
                annual_heat_gain_kwh=round(transmitted + cond_gain, 1),
                annual_heat_loss_kwh=round(cond_loss, 1),
                peak_heat_gain_rate_w=round(area_m2 * shgc * building.peak_poa(face.orientation), 1),
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


def _cooling_elec(window_cooling_thermal: float, cooling_cop: float) -> float:
    return window_cooling_thermal * COOLING_PICKUP / (cooling_cop * SEASONAL_COP_DERATE)


def _monthly_window_cooling(
    project: EngineProject, shgc_provider, cooling_cop: float
) -> list[float]:
    """12 monthly window-driven cooling-electricity values (kWh, Jan..Dec)."""
    poa = weather.monthly_poa_by_face(project.zip, project.climate_zone)
    weights = _cooling_weights(project.climate_zone)
    monthly = [0.0] * 12
    for face in project.faces:
        base = datastore.get_base_glazing(face.base_glazing_id)
        if base is None:
            continue
        area_m2 = face.area_sqft * SF_TO_M2
        shgc = shgc_provider(base)
        months = poa.get(face.orientation, [0.0] * 12)
        for m in range(12):
            thermal = months[m] * area_m2 * shgc * weights[m]
            monthly[m] += thermal * COOLING_PICKUP / (cooling_cop * SEASONAL_COP_DERATE)
    return monthly


def _make_run(
    label: str,
    end_uses: EnergyEndUses,
    station: str,
    windows: list[WindowSurfaceResult],
    monthly: list[float] | None = None,
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
        monthly_cooling_kwh=[round(x, 1) for x in (monthly or [])],
        warnings=[ESTIMATE_WARNING],
    )


def run_project(project: EngineProject) -> tuple[RunResult, list[RunResult]]:
    """Produce a baseline RunResult and one per candidate film (estimate mode)."""
    meta = datastore.get_prototype(project.building_type)
    if meta is None:
        raise KeyError(f"Unknown building_type: {project.building_type!r}")
    z = datastore.get_zip(project.zip)
    station = z["station_city"] if z else "Unknown"

    # Resolve as-built HVAC / envelope / operations against prototype + climate
    # defaults. The cooling COP is the dominant lever on $ savings.
    bldg = building.resolve(project, meta)

    proto = _baseline_end_uses(meta, project.gross_floor_area_sf)
    # Split the prototype's cooling into a non-window portion (kept fixed) and a
    # window-solar portion (recomputed from the project's actual glazing).
    nonwindow_cooling = proto.cooling_elec_kwh * NONWINDOW_COOLING_FRACTION

    def base_shgc(base):
        return float(base["shgc"])

    base_cool_thermal, _ = _window_solar_loads(project, base_shgc)
    baseline_window_cooling = _cooling_elec(base_cool_thermal, bldg.cooling_cop)

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
    nonwindow_month = nonwindow_cooling / 12.0
    base_monthly = [nonwindow_month + x for x in _monthly_window_cooling(project, base_shgc, bldg.cooling_cop)]
    baseline = _make_run(
        "baseline", base_uses, station,
        _window_results(project, lambda b: glazing.base_properties(b), bldg),
        monthly=base_monthly,
    )

    baseline_vt = _avg_vt(project, lambda b: glazing.base_properties(b))
    daylit_fraction = DAYLIT_FRACTION.get(project.building_type, 0.25)

    film_runs: list[RunResult] = []
    for scenario in project.scenarios:
        film = resolve_film(scenario.film_sku)

        def applied_shgc(base, _film=film):
            return glazing.applied_properties(base, _film).shgc

        film_cool_thermal, film_heat_thermal = _window_solar_loads(project, applied_shgc)
        _, base_heat_thermal = _window_solar_loads(project, base_shgc)
        film_window_cooling = _cooling_elec(film_cool_thermal, bldg.cooling_cop)
        # Lost beneficial winter solar gain becomes a heating penalty.
        heating_penalty = max(0.0, base_heat_thermal - film_heat_thermal) * HEATING_PICKUP / bldg.heating_cop

        # Daylighting penalty: cutting visible transmittance makes daylit zones
        # run electric lighting more (partially offsets cooling savings).
        film_vt = _avg_vt(project, lambda b, _f=film: glazing.applied_properties(b, _f))
        vt_drop = max(0.0, (baseline_vt - film_vt) / baseline_vt) if baseline_vt else 0.0
        lighting_penalty = (
            proto.interior_lighting_kwh * daylit_fraction * vt_drop * DAYLIGHT_CONTROL_EFFECTIVENESS
        )

        film_cooling = nonwindow_cooling + film_window_cooling
        film_heating = proto.heating_elec_kwh + heating_penalty
        film_lighting = proto.interior_lighting_kwh + lighting_penalty
        film_uses = EnergyEndUses(
            heating_elec_kwh=round(film_heating, 1),
            cooling_elec_kwh=round(film_cooling, 1),
            interior_lighting_kwh=round(film_lighting, 1),
            interior_equipment_kwh=proto.interior_equipment_kwh,
            fans_kwh=proto.fans_kwh,
            total_electricity_kwh=round(
                proto.total_electricity_kwh
                - proto.cooling_elec_kwh
                + film_cooling
                + heating_penalty
                + lighting_penalty,
                1,
            ),
            total_gas_kwh=0.0,
        )
        film_monthly = [
            nonwindow_month + x
            for x in _monthly_window_cooling(project, applied_shgc, bldg.cooling_cop)
        ]
        film_runs.append(
            _make_run(
                scenario.label, film_uses, station,
                _window_results(project, lambda b, _f=film: glazing.applied_properties(b, _f), bldg),
                monthly=film_monthly,
            )
        )
    return baseline, film_runs

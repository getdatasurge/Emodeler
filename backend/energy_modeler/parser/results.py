"""Assemble the per-film comparison from baseline + candidate RunResults
(spec Ch 6.3/6.4/6.5). Engine-agnostic: works on RunResults from either the
EnergyPlus parser or the analytical estimate."""
from __future__ import annotations

import dataclasses
import math
import uuid
from datetime import datetime, timezone

from .. import carbon, datastore, economics
from ..engine import building
from ..engine.inputs import EngineProject
from ..schemas import (
    AppendixGComparison,
    EnergyEndUses,
    FilmComparison,
    PeakDemand,
    ProjectComparison,
    RunResult,
)
from .eplus_html import parse_annual_end_uses


def _nan_to_none(value: float) -> float:
    """Replace NaN with a JSON-safe sentinel (-1) for payback/IRR display."""
    return -1.0 if math.isnan(value) else round(value, 4)


_ENDUSE_FIELD = {
    "heating": "heating_elec_kwh",
    "cooling": "cooling_elec_kwh",
    "interior_lighting": "interior_lighting_kwh",
    "interior_equipment": "interior_equipment_kwh",
    "fans": "fans_kwh",
    "pumps": "pumps_kwh",
    "heat_rejection": "heat_rejection_kwh",
}


def parse_run(
    run_dir,
    label: str,
    *,
    station: str = "EnergyPlus run",
    weather_dataset: str = "TMY3 (EnergyPlus)",
    energyplus_version: str = "22.1.0",
) -> RunResult:
    """Build a RunResult from an EnergyPlus run directory's eplustbl.csv summary
    (spec Ch 6.2). Per-window + hourly detail is layered on by eplus_csv."""
    categories = parse_annual_end_uses(run_dir)
    eu = EnergyEndUses()
    total_elec = 0.0
    total_gas = 0.0
    for cat, vals in categories.items():
        elec = vals.get("electricity_kwh", 0.0)
        gas = vals.get("gas_kwh", 0.0)
        field = _ENDUSE_FIELD.get(cat)
        if field:
            setattr(eu, field, round(elec, 1))
        if cat in ("total_end_uses", "total"):
            total_elec = elec
            total_gas = gas
        else:
            total_gas += gas
    eu.heating_gas_kwh = round(categories.get("heating", {}).get("gas_kwh", 0.0), 1)
    eu.total_electricity_kwh = round(
        total_elec or sum(getattr(eu, f) for f in _ENDUSE_FIELD.values()), 1
    )
    eu.total_gas_kwh = round(total_gas, 1)
    return RunResult(
        run_id=str(uuid.uuid4()),
        scenario_label=label,
        engine_mode="energyplus",
        energyplus_version=energyplus_version,
        weather_station=station,
        weather_dataset=weather_dataset,
        annual_end_uses=eu,
        peak_demand=PeakDemand(
            cooling_peak_kw=round(eu.cooling_elec_kwh / 1800.0, 2),
            total_facility_peak_kw=round(eu.total_electricity_kwh / 2600.0, 2),
        ),
        windows=[],
        warnings=[],
    )


_KWH_PER_THERM = 29.3001  # 1 therm = 100,000 BTU; 1 kWh = 3412.14 BTU


def build_comparison(
    project: EngineProject,
    baseline: RunResult,
    film_runs: list[RunResult],
    engine_mode: str,
    *,
    appendix_g_run: RunResult | None = None,
) -> ProjectComparison:
    rate = project.utility_rate_usd_kwh
    gas_rate = project.gas_rate_usd_therm  # $/therm; None -> gas dollars = 0
    opts = project.options
    films: list[FilmComparison] = []

    for idx, run in enumerate(film_runs):
        scenario = project.scenarios[idx] if idx < len(project.scenarios) else None
        cost = scenario.installed_cost_usd if scenario else 0.0
        sku = scenario.film_sku if scenario else run.scenario_label

        be = baseline.annual_end_uses
        fe = run.annual_end_uses
        delta_cooling = round(be.cooling_elec_kwh - fe.cooling_elec_kwh, 1)
        delta_heating = round(be.heating_elec_kwh - fe.heating_elec_kwh, 1)
        delta_lighting = round(be.interior_lighting_kwh - fe.interior_lighting_kwh, 1)
        delta_total = round(be.total_electricity_kwh - fe.total_electricity_kwh, 1)
        # Gas savings in kWh-equivalent (1 therm = 29.3 kWh). Negative when the
        # film slightly increases heating demand (the typical winter penalty).
        delta_gas_kwh = round(be.total_gas_kwh - fe.total_gas_kwh, 1)
        delta_peak = round(
            baseline.peak_demand.cooling_peak_kw - run.peak_demand.cooling_peak_kw, 3
        )
        demand_savings = (
            economics.annual_demand_savings(delta_peak, opts.demand_charge_usd_per_kw)
            if opts.include_demand_charge
            else 0.0
        )
        # Dollar savings = electric kWh saved at the elec rate + gas therms saved
        # at the gas rate (when set) + optional demand-charge component.
        gas_dollars = (delta_gas_kwh / _KWH_PER_THERM) * gas_rate if gas_rate else 0.0
        delta_cost = round(delta_total * rate + gas_dollars + demand_savings, 2)
        delta_co2 = round(carbon.lb_co2_avoided(delta_total, project.zip), 1)
        delta_co2e = round(carbon.co2e_kg_avoided(delta_total, project.zip), 1)

        monthly_savings: list[float] = []
        if len(baseline.monthly_cooling_kwh) == 12 and len(run.monthly_cooling_kwh) == 12:
            monthly_savings = [
                round(b - f, 1)
                for b, f in zip(baseline.monthly_cooling_kwh, run.monthly_cooling_kwh)
            ]

        payback = economics.simple_payback(cost, delta_cost)
        npv = economics.npv(
            delta_cost, opts.film_life_yrs, opts.discount_rate, cost, opts.utility_escalation
        )
        irr_pct = economics.percent(
            economics.irr(delta_cost, opts.film_life_yrs, cost, opts.utility_escalation)
        )

        films.append(
            FilmComparison(
                scenario_label=run.scenario_label,
                film_sku=sku,
                delta_cooling_kwh=delta_cooling,
                delta_heating_kwh=delta_heating,
                delta_lighting_kwh=delta_lighting,
                delta_total_kwh=delta_total,
                delta_gas_kwh=delta_gas_kwh,
                delta_peak_kw=delta_peak,
                delta_cost_usd_per_year=delta_cost,
                delta_co2_lb_per_year=delta_co2,
                delta_co2e_kg_per_year=delta_co2e,
                project_cost_usd=cost,
                simple_payback_years=_nan_to_none(payback),
                npv_15yr_usd=round(npv, 2),
                irr_15yr_pct=_nan_to_none(irr_pct),
                monthly_cooling_savings_kwh=monthly_savings,
            )
        )

    proto = datastore.get_prototype(project.building_type)
    resolved_building = (
        dataclasses.asdict(building.resolve(project, proto)) if proto else None
    )

    # ASHRAE 90.1-2019 Appendix G baseline anchor for LEED PCI. We compute
    # both total + cooling-only % savings since the cooling-only number is
    # less noisy when the prototype's lighting / equipment dominates the EUI.
    appG: AppendixGComparison | None = None
    if appendix_g_run is not None:
        from ..engine.appendix_g import baseline_spec

        spec = baseline_spec(
            project.building_type, project.climate_zone,
            int(proto.get("floors", 1) or 1) if proto else 1,
            project.gross_floor_area_sf,
        )
        appG_total = appendix_g_run.annual_end_uses.total_electricity_kwh
        appG_cool = appendix_g_run.annual_end_uses.cooling_elec_kwh
        proj_total = baseline.annual_end_uses.total_electricity_kwh
        proj_cool = baseline.annual_end_uses.cooling_elec_kwh
        pct_total = (
            round((appG_total - proj_total) / appG_total * 100.0, 2)
            if appG_total > 0 else 0.0
        )
        pct_cool = (
            round((appG_cool - proj_cool) / appG_cool * 100.0, 2)
            if appG_cool > 0 else 0.0
        )
        appG = AppendixGComparison(
            run=appendix_g_run,
            window_u_factor=spec.window_u_factor,
            window_shgc=spec.window_shgc,
            pct_savings_vs_code_baseline=pct_total,
            cooling_pct_savings_vs_code_baseline=pct_cool,
        )

    warnings = list(baseline.warnings)
    return ProjectComparison(
        project_id=project.project_id,
        engine_mode=engine_mode,
        baseline=baseline,
        films=films,
        film_runs=film_runs,
        appendix_g=appG,
        building=resolved_building,
        generated_at=datetime.now(timezone.utc),
        warnings=warnings,
    )

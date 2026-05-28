"""Assemble the per-film comparison from baseline + candidate RunResults
(spec Ch 6.3/6.4/6.5). Engine-agnostic: works on RunResults from either the
EnergyPlus parser or the analytical estimate."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from .. import carbon, economics
from ..engine.inputs import EngineProject
from ..schemas import FilmComparison, ProjectComparison, RunResult


def _nan_to_none(value: float) -> float:
    """Replace NaN with a JSON-safe sentinel (-1) for payback/IRR display."""
    return -1.0 if math.isnan(value) else round(value, 4)


def build_comparison(
    project: EngineProject,
    baseline: RunResult,
    film_runs: list[RunResult],
    engine_mode: str,
) -> ProjectComparison:
    rate = project.utility_rate_usd_kwh
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
        delta_peak = round(
            baseline.peak_demand.cooling_peak_kw - run.peak_demand.cooling_peak_kw, 3
        )
        delta_cost = round(delta_total * rate, 2)
        delta_co2 = round(carbon.lb_co2_avoided(delta_total, project.zip), 1)

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
                delta_peak_kw=delta_peak,
                delta_cost_usd_per_year=delta_cost,
                delta_co2_lb_per_year=delta_co2,
                project_cost_usd=cost,
                simple_payback_years=_nan_to_none(payback),
                npv_15yr_usd=round(npv, 2),
                irr_15yr_pct=_nan_to_none(irr_pct),
            )
        )

    warnings = list(baseline.warnings)
    return ProjectComparison(
        project_id=project.project_id,
        engine_mode=engine_mode,
        baseline=baseline,
        films=films,
        film_runs=film_runs,
        generated_at=datetime.now(timezone.utc),
        warnings=warnings,
    )

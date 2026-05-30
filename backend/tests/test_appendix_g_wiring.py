"""Appendix G baseline plumbing: parser_bridge.run_real_pipeline returns a 4th
element (the appG run when CalcOptions.include_appendix_g_baseline=true) and
build_comparison computes pct_savings_vs_code_baseline + cooling_pct_savings
from it. The fallback estimate path returns appG=None unconditionally."""
from energy_modeler.engine import runner
from energy_modeler.engine.inputs import (
    EngineFace,
    EngineOptions,
    EngineProject,
    EngineScenario,
)
from energy_modeler.parser.results import build_comparison
from energy_modeler.schemas import EnergyEndUses, PeakDemand, RunResult


def _project(*, include_appendix_g: bool) -> EngineProject:
    return EngineProject(
        project_id="appg", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540", utility_rate_usd_kwh=0.1145,
        egrid_subregion="FRCC",
        faces=[EngineFace("S", 873, "dbl_clear_3mm_13mmAir")],
        scenarios=[EngineScenario("Good", "3M-PR40X", 25000)],
        options=EngineOptions(include_appendix_g_baseline=include_appendix_g),
    )


def _run(label: str, cooling: float, total: float) -> RunResult:
    return RunResult(
        run_id=label, scenario_label=label, engine_mode="energyplus",
        energyplus_version="22.1.0", weather_station="TPA",
        weather_dataset="TMY3",
        annual_end_uses=EnergyEndUses(
            cooling_elec_kwh=cooling, total_electricity_kwh=total,
        ),
        peak_demand=PeakDemand(),
        windows=[], monthly_cooling_kwh=[cooling / 12] * 12, warnings=[],
    )


def test_runner_returns_4tuple_with_appG_none_on_estimate_fallback():
    """No EnergyPlus binary -> analytical estimate. The 4th element is always
    None — the estimate is not the ASHRAE-140-validated engine PCI requires."""
    project = _project(include_appendix_g=True)
    mode, baseline, films, appG_run = runner.run_project(project)
    assert mode == "analytical_estimate"
    assert appG_run is None
    assert baseline is not None


def test_build_comparison_populates_appendix_g_with_two_pct_savings():
    """When build_comparison gets a synthetic appG run, it computes
    pct_savings_vs_code_baseline (total) and cooling_pct_savings (cooling
    only) from the difference, and populates the schema's window U / SHGC
    from the climate-zone lookup."""
    project = _project(include_appendix_g=True)
    baseline = _run("baseline", cooling=80000.0, total=170000.0)
    appG_run = _run("appG", cooling=100000.0, total=190000.0)
    cmp = build_comparison(
        project, baseline, [], "energyplus", appendix_g_run=appG_run,
    )
    assert cmp.appendix_g is not None
    assert cmp.appendix_g.run.scenario_label == "appG"
    # Cooling: (100000-80000)/100000 = 20.0
    assert cmp.appendix_g.cooling_pct_savings_vs_code_baseline == 20.0
    # Total: (190000-170000)/190000 = 10.53
    assert abs(cmp.appendix_g.pct_savings_vs_code_baseline - 10.53) < 0.05
    # Climate Zone 2 (Tampa) prescriptive vertical fenestration: SHGC 0.25,
    # U ~ 0.50 BTU/h.ft^2.F per Table G3.4.
    assert cmp.appendix_g.window_shgc == 0.25
    assert 0.45 < cmp.appendix_g.window_u_factor <= 0.55


def test_build_comparison_appendix_g_absent_when_no_run_passed():
    project = _project(include_appendix_g=False)
    baseline = _run("baseline", cooling=80000.0, total=170000.0)
    cmp = build_comparison(project, baseline, [], "energyplus")
    assert cmp.appendix_g is None


def test_build_comparison_handles_zero_appendix_g_division_gracefully():
    """If for any reason the appG run reports zero total electricity, the
    pct calc must not divide-by-zero."""
    project = _project(include_appendix_g=True)
    baseline = _run("baseline", cooling=80000.0, total=170000.0)
    appG_run = _run("appG", cooling=0.0, total=0.0)
    cmp = build_comparison(
        project, baseline, [], "energyplus", appendix_g_run=appG_run,
    )
    assert cmp.appendix_g is not None
    assert cmp.appendix_g.pct_savings_vs_code_baseline == 0.0
    assert cmp.appendix_g.cooling_pct_savings_vs_code_baseline == 0.0

"""Engine validation against the spec §12.1 fixture inputs.

The strict §12.1 output ranges are validated when the EnergyPlus binary is
present. Here we exercise the labeled analytical fallback and assert physical
self-consistency + plausibility (savings positive and bounded by baseline,
cold-climate heating penalty present, finite economics)."""
import math

import pytest

from energy_modeler.engine import runner
from energy_modeler.engine.inputs import EngineFace, EngineProject, EngineScenario
from energy_modeler.parser import results


def _project(**kw):
    return EngineProject(egrid_subregion="X", **kw)


def _run(project):
    mode, baseline, films = runner.run_project(project)
    return mode, baseline, results.build_comparison(project, baseline, films, mode)


def test_fx01_zephyrhills_plausible():
    proj = _project(
        project_id="fx01", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540", utility_rate_usd_kwh=0.1145,
        faces=[EngineFace(o, a, "dbl_clear_3mm_13mmAir")
               for o, a in [("S", 873), ("E", 873), ("W", 874), ("N", 874)]],
        scenarios=[EngineScenario("PR40X", "3M-PR40X", 43675)],
    )
    mode, baseline, comp = _run(proj)
    assert mode == "analytical_estimate"
    f = comp.films[0]
    assert f.delta_cooling_kwh > 0
    # Savings can never exceed baseline cooling (physical self-consistency).
    assert f.delta_cooling_kwh <= baseline.annual_end_uses.cooling_elec_kwh
    assert f.delta_total_kwh > 0
    assert f.delta_co2_lb_per_year > 0
    assert f.delta_co2e_kg_per_year > 0
    # Monthly cooling-savings profile sums to the annual cooling delta.
    assert len(f.monthly_cooling_savings_kwh) == 12
    assert abs(sum(f.monthly_cooling_savings_kwh) - f.delta_cooling_kwh) < 5.0
    assert not math.isnan(f.simple_payback_years) and f.simple_payback_years > 0
    # Loose envelope around the dealer Excel sanity point ($5,594/yr, 7.8 yr).
    assert 3000 < f.delta_cost_usd_per_year < 9000


def test_cold_climate_has_heating_penalty():
    proj = _project(
        project_id="fx02", building_type="SecondarySchool", climate_zone="6A",
        gross_floor_area_sf=210000, zip="55303", utility_rate_usd_kwh=0.105,
        faces=[EngineFace(o, a, "dbl_lowE_3mm_13mmAir")
               for o, a in [("S", 6000), ("E", 5000), ("W", 5000), ("N", 4000)]],
        scenarios=[EngineScenario("NV35", "3M-NV35", 180000)],
    )
    _, _, comp = _run(proj)
    f = comp.films[0]
    assert f.delta_heating_kwh < 0  # winter solar gain lost -> heating penalty
    assert f.delta_cooling_kwh > 0


def test_good_better_best_ordering():
    proj = _project(
        project_id="gbb", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=20000, zip="33540", utility_rate_usd_kwh=0.1145,
        faces=[EngineFace("S", 2000, "dbl_clear_3mm_13mmAir")],
        scenarios=[
            EngineScenario("Aggressive", "3M-NV15", 30000),  # SHGC 0.21 (most rejection)
            EngineScenario("Balanced", "3M-PR70X", 30000),   # SHGC 0.34 (least rejection)
        ],
    )
    _, _, comp = _run(proj)
    by = {f.scenario_label: f for f in comp.films}
    # Lower-SHGC film rejects more solar -> larger cooling savings.
    assert by["Aggressive"].delta_cooling_kwh > by["Balanced"].delta_cooling_kwh


def test_cooling_cop_scales_savings_and_echoes_provenance():
    base_kw = dict(
        project_id="cop", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540", utility_rate_usd_kwh=0.1145,
        faces=[EngineFace(o, a, "dbl_clear_3mm_13mmAir") for o, a in [("S", 873), ("W", 874)]],
        scenarios=[EngineScenario("Good", "3M-PR40X", 20000)],
    )
    low = _run(_project(hvac_cooling_cop=2.5, **base_kw))[2]
    high = _run(_project(hvac_cooling_cop=5.0, **base_kw))[2]
    # A less efficient cooling system saves more $ per unit of solar rejected.
    assert low.films[0].delta_cost_usd_per_year > high.films[0].delta_cost_usd_per_year
    # Resolved building echoes the user COP and flags un-supplied fields as default.
    assert low.building["cooling_cop"] == 2.5
    assert low.building["sources"]["cooling_cop"] == "user"
    assert low.building["sources"]["wall_u_factor"] == "default"


def test_window_conduction_and_orientation_peaks():
    proj = _project(
        project_id="cond", building_type="MediumOffice", climate_zone="6A",
        gross_floor_area_sf=20000, zip="55303", utility_rate_usd_kwh=0.105,
        faces=[EngineFace("W", 1000, "dbl_clear_3mm_13mmAir"),
               EngineFace("N", 1000, "dbl_clear_3mm_13mmAir")],
        scenarios=[EngineScenario("Good", "3M-PR40X", 20000)],
    )
    _, baseline, _ = _run(proj)
    by_orient = {x.surface_name.split("_")[1]: x for x in baseline.windows}
    # Cold climate -> winter conduction loss is now populated (was hard-coded 0).
    assert all(x.annual_heat_loss_kwh > 0 for x in baseline.windows)
    # West sees a higher cooling-design peak than north.
    assert by_orient["W"].peak_heat_gain_rate_w > by_orient["N"].peak_heat_gain_rate_w


def test_thinsulate_improves_u_factor_standard_film_does_not():
    from energy_modeler import datastore
    from energy_modeler.engine import glazing
    from energy_modeler.engine.film_catalog import resolve as resolve_film

    base = datastore.get_base_glazing("dbl_clear_3mm_13mmAir")
    base_u = base["u_factor_btuhrft2F"]
    th = glazing.applied_properties(base, resolve_film("3M-TH40"))  # Thinsulate low-e
    pr = glazing.applied_properties(base, resolve_film("3M-PR40X"))  # solar-control
    # FX-03 case: a U-improving film lowers the assembly U; a standard solar
    # film leaves U ~unchanged (spec 0.5.10).
    assert th.u_factor_btuhrft2F < base_u
    assert pr.u_factor_btuhrft2F == base_u


def test_daylighting_penalty_present():
    proj = _project(
        project_id="dl", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540", utility_rate_usd_kwh=0.1145,
        faces=[EngineFace("S", 1500, "dbl_clear_3mm_13mmAir")],
        scenarios=[EngineScenario("Good", "3M-PR40X", 20000)],  # VT 0.78 -> ~0.31
    )
    _, _, comp = _run(proj)
    # Cutting visible transmittance makes daylit zones run electric lighting
    # more -> a lighting penalty (delta = baseline - film < 0).
    assert comp.films[0].delta_lighting_kwh < 0


def test_unknown_film_raises():
    proj = _project(
        project_id="bad", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=10000, zip="33540", utility_rate_usd_kwh=0.11,
        faces=[EngineFace("S", 1000, "dbl_clear_3mm_13mmAir")],
        scenarios=[EngineScenario("X", "3M-NOPE", 1000)],
    )
    with pytest.raises(KeyError):
        runner.run_project(proj)

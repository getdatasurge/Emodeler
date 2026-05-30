"""Operating-hours-per-week now drives the analytical fallback baseline EUI:
a 24/7 datacenter no longer reports the prototype's 55-hr office EUI just
because the prototype defaults to 55 hr. EnergyPlus path uses the
prototype's own Schedule:Compact objects; that's documented as a known gap."""
import pytest

from energy_modeler.engine import runner
from energy_modeler.engine.inputs import EngineFace, EngineProject, EngineScenario


def _project(hours: float | None) -> EngineProject:
    return EngineProject(
        project_id="ops", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540",
        utility_rate_usd_kwh=0.1145, egrid_subregion="FRCC",
        faces=[EngineFace("S", 873, "dbl_clear_3mm_13mmAir")],
        scenarios=[EngineScenario("Good", "3M-PR40X", 25000)],
        operating_hours_per_week=hours,
    )


def test_24x7_operations_scale_baseline_above_prototype():
    """MediumOffice prototype is 55 hr/wk. A 24/7 (168 hr) facility should
    report a materially higher baseline electricity total because internal
    loads + HVAC track operating hours."""
    _, default_baseline, _, _ = runner.run_project(_project(hours=None))
    _, around_clock, _, _ = runner.run_project(_project(hours=168))
    assert (
        around_clock.annual_end_uses.total_electricity_kwh
        > default_baseline.annual_end_uses.total_electricity_kwh * 1.5
    )


def test_reduced_hours_scale_baseline_below_prototype():
    """A 30 hr/wk part-time facility comes in BELOW the prototype baseline."""
    _, proto_default, _, _ = runner.run_project(_project(hours=None))
    _, part_time, _, _ = runner.run_project(_project(hours=30))
    assert (
        part_time.annual_end_uses.total_electricity_kwh
        < proto_default.annual_end_uses.total_electricity_kwh * 0.7
    )


def test_extreme_input_clamped_to_sane_band():
    """Typo guard: 10000 hr/wk shouldn't 200x the result. The clamp keeps
    the factor within [0.25, 4.0]."""
    _, default_baseline, _, _ = runner.run_project(_project(hours=None))
    _, typo, _, _ = runner.run_project(_project(hours=10000))
    assert (
        typo.annual_end_uses.total_electricity_kwh
        <= default_baseline.annual_end_uses.total_electricity_kwh * 4.1
    )


def test_missing_operating_hours_uses_prototype_default():
    """When hours=None, the prototype default is used (factor 1.0)."""
    _, baseline, _, _ = runner.run_project(_project(hours=None))
    # Sanity: the run completed with a reasonable baseline.
    assert baseline.annual_end_uses.total_electricity_kwh > 0


def test_resolved_building_records_user_vs_default_provenance():
    """The hours field's 'user' vs 'default' provenance flows into the audit
    sources map so the report's modeling-assumptions panel can mark it."""
    from energy_modeler import datastore
    from energy_modeler.engine import building

    meta = datastore.get_prototype("MediumOffice")
    user_set = building.resolve(_project(hours=70), meta)
    default_set = building.resolve(_project(hours=None), meta)
    assert user_set.sources["operating_hours_per_week"] == "user"
    assert default_set.sources["operating_hours_per_week"] == "default"


@pytest.mark.parametrize("hours", [12, 40, 84, 168])
def test_total_scales_monotonically_with_hours(hours):
    """Sanity: total goes up with hours (within the clamp)."""
    _, baseline_lower, _, _ = runner.run_project(_project(hours=max(12, hours - 12)))
    _, baseline_at, _, _ = runner.run_project(_project(hours=hours))
    assert (
        baseline_at.annual_end_uses.total_electricity_kwh
        >= baseline_lower.annual_end_uses.total_electricity_kwh - 1.0
    )

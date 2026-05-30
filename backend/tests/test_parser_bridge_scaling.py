"""Prototype-to-project floor-area scaling (parser_bridge._scale_run /
_scale_factor). The DOE prototype runs at its nominal floor area; without this
rescale the reported energies belong to the prototype, not the project. EFILM
applies the same scale — we expose it explicitly and surface the factor on
every RunResult's warnings so the audit bundle records the math."""
from energy_modeler.engine.inputs import EngineProject
from energy_modeler.engine.parser_bridge import _scale_factor, _scale_run
from energy_modeler.schemas import EnergyEndUses, PeakDemand, RunResult


def _project(area_sf: float) -> EngineProject:
    return EngineProject(
        project_id="x", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=area_sf, zip="33540",
        utility_rate_usd_kwh=0.1145, egrid_subregion="FRCC",
    )


def _run(cooling_kwh: float = 80000.0) -> RunResult:
    return RunResult(
        run_id="r", scenario_label="x", engine_mode="energyplus",
        energyplus_version="22.1.0", weather_station="TPA",
        weather_dataset="TMY3", annual_end_uses=EnergyEndUses(
            cooling_elec_kwh=cooling_kwh, heating_elec_kwh=4000.0,
            interior_lighting_kwh=45000.0, interior_equipment_kwh=100000.0,
            fans_kwh=25000.0, total_electricity_kwh=cooling_kwh + 174000.0,
        ),
        peak_demand=PeakDemand(cooling_peak_kw=44.4, total_facility_peak_kw=100.0),
        windows=[], monthly_cooling_kwh=[cooling_kwh / 12] * 12, warnings=[],
    )


def test_scale_factor_is_project_over_prototype():
    factor, project_sf, proto_sf = _scale_factor(
        _project(14500), {"nominal_area_sf": 53000}
    )
    assert factor == 14500 / 53000
    assert project_sf == 14500 and proto_sf == 53000


def test_scale_factor_defaults_to_one_on_missing_inputs():
    assert _scale_factor(_project(14500), {})[0] == 1.0
    assert _scale_factor(_project(0), {"nominal_area_sf": 53000})[0] == 1.0


def test_scale_run_applies_uniformly_to_kwh_and_peak():
    rr = _run(cooling_kwh=80000.0)
    _scale_run(rr, 0.5)
    eu = rr.annual_end_uses
    assert eu.cooling_elec_kwh == 40000.0
    assert eu.heating_elec_kwh == 2000.0
    assert eu.interior_lighting_kwh == 22500.0
    assert eu.total_electricity_kwh == 127000.0
    assert rr.peak_demand.cooling_peak_kw == 22.2
    assert rr.peak_demand.total_facility_peak_kw == 50.0
    # Monthly profile scales too (cooling delta UI uses it).
    assert all(abs(v - 80000.0 / 12 * 0.5) < 0.1 for v in rr.monthly_cooling_kwh)


def test_scale_run_factor_one_is_noop():
    rr = _run(cooling_kwh=80000.0)
    before = rr.annual_end_uses.cooling_elec_kwh
    _scale_run(rr, 1.0)
    assert rr.annual_end_uses.cooling_elec_kwh == before

"""Gas heating savings priced at the gas rate (not the electric rate).

The MediumOffice prototype has gas-fired heating. Pre-fix, build_comparison
priced ALL energy at the electric $/kWh, so dollar savings on gas-heated
buildings were materially wrong. With gas_rate_usd_therm set, gas savings
contribute (delta_gas_kwh / 29.3001) * gas_rate to delta_cost_usd_per_year;
absent the rate they contribute $0 (the prior all-electric behavior, safe
for all-electric projects)."""
from energy_modeler.engine.inputs import EngineFace, EngineProject, EngineScenario
from energy_modeler.parser.results import _KWH_PER_THERM, build_comparison
from energy_modeler.schemas import EnergyEndUses, PeakDemand, RunResult


def _project(gas_rate: float | None) -> EngineProject:
    return EngineProject(
        project_id="x", building_type="MediumOffice", climate_zone="6A",
        gross_floor_area_sf=20000, zip="55303",
        utility_rate_usd_kwh=0.105,
        gas_rate_usd_therm=gas_rate,
        egrid_subregion="MROW",
        faces=[EngineFace("S", 600, "dbl_clear_3mm_13mmAir")],
        scenarios=[EngineScenario("Good", "3M-PR40X", 25000)],
    )


def _run(label: str, total_elec: float, total_gas: float) -> RunResult:
    return RunResult(
        run_id=label, scenario_label=label, engine_mode="energyplus",
        energyplus_version="22.1.0", weather_station="MSP",
        weather_dataset="TMY3",
        annual_end_uses=EnergyEndUses(
            cooling_elec_kwh=20000.0, heating_elec_kwh=5000.0,
            interior_lighting_kwh=30000.0, fans_kwh=8000.0,
            total_electricity_kwh=total_elec,
            heating_gas_kwh=total_gas, total_gas_kwh=total_gas,
        ),
        peak_demand=PeakDemand(cooling_peak_kw=10.0, total_facility_peak_kw=30.0),
        windows=[], monthly_cooling_kwh=[1667.0] * 12, warnings=[],
    )


def test_gas_savings_priced_at_gas_rate_when_set():
    # 4,000 kWh-equivalent of gas saved at $1.20/therm.
    # = 4000 / 29.3001 = 136.52 therms = $163.82
    # Electric savings: 100 kWh * $0.105 = $10.50. Total = $174.32.
    proj = _project(gas_rate=1.20)
    baseline = _run("baseline", total_elec=63000.0, total_gas=20000.0)
    film = _run("Good", total_elec=62900.0, total_gas=16000.0)
    cmp = build_comparison(proj, baseline, [film], engine_mode="energyplus")
    f = cmp.films[0]
    assert f.delta_gas_kwh == 4000.0
    expected = round(100 * 0.105 + (4000.0 / _KWH_PER_THERM) * 1.20, 2)
    assert f.delta_cost_usd_per_year == expected
    assert abs(expected - 174.32) < 0.1


def test_no_gas_rate_means_gas_contributes_zero_dollars():
    """Without gas_rate_usd_therm set, the comparison must match the prior
    all-electric pricing (gas reported in kWh, never priced)."""
    proj = _project(gas_rate=None)
    baseline = _run("baseline", total_elec=63000.0, total_gas=20000.0)
    film = _run("Good", total_elec=62900.0, total_gas=16000.0)
    cmp = build_comparison(proj, baseline, [film], engine_mode="energyplus")
    f = cmp.films[0]
    assert f.delta_gas_kwh == 4000.0  # still reported for transparency
    # Only the 100 kWh electric delta * $0.105 = $10.50.
    assert f.delta_cost_usd_per_year == 10.5


def test_negative_gas_delta_is_a_dollar_cost_not_a_savings():
    """The winter heating penalty: film reduces solar heat gain, so a gas-
    heated building burns more gas in January. The dollar impact must reduce
    delta_cost (it's a partial offset, not a savings)."""
    proj = _project(gas_rate=1.20)
    baseline = _run("baseline", total_elec=63000.0, total_gas=20000.0)
    # Film increases gas use by 1,500 kWh-equivalent (penalty).
    film = _run("Good", total_elec=62900.0, total_gas=21500.0)
    cmp = build_comparison(proj, baseline, [film], engine_mode="energyplus")
    f = cmp.films[0]
    assert f.delta_gas_kwh == -1500.0
    # Electric: +$10.50. Gas: -1500/29.3001 * 1.20 = -$61.43. Net = -$50.93.
    assert f.delta_cost_usd_per_year < 0

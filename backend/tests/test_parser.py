"""Week 08: parse_run builds a RunResult from an EnergyPlus eplustbl.csv summary.

Pure file parsing — validated against a realistic fixture, no binary needed."""
from energy_modeler.parser.results import parse_run

# Mirrors EnergyPlus's eplustbl.csv: spaced report/table titles, an End Uses
# block with the electricity column first.
EPLUSTBL = """REPORT:,Annual Building Utility Performance Summary,Entire Facility
FOR:,Entire Facility,

End Uses,
,Electricity [kWh],Natural Gas [kWh],District Heating [kWh],District Cooling [kWh]
Heating,13572.0,1500.0,0.0,0.0
Cooling,80553.9,0.0,0.0,0.0
Interior Lighting,45240.0,0.0,0.0,0.0
Interior Equipment,101790.0,0.0,0.0,0.0
Fans,24882.0,0.0,0.0,0.0
Total End Uses,266037.9,1500.0,0.0,0.0
"""


def test_parse_run_from_eplustbl(tmp_path):
    (tmp_path / "eplustbl.csv").write_text(EPLUSTBL)
    rr = parse_run(tmp_path, "baseline", station="TAMPA INTL AP")

    assert rr.engine_mode == "energyplus"
    eu = rr.annual_end_uses
    assert eu.cooling_elec_kwh == 80553.9
    assert eu.heating_elec_kwh == 13572.0
    assert eu.interior_lighting_kwh == 45240.0
    assert eu.interior_equipment_kwh == 101790.0
    assert eu.fans_kwh == 24882.0
    assert eu.total_electricity_kwh == 266037.9
    assert eu.heating_gas_kwh == 1500.0
    assert rr.peak_demand.cooling_peak_kw > 0

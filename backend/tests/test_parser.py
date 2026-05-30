"""Week 08: parse_run builds a RunResult from an EnergyPlus eplustbl.csv summary.

Pure file parsing — validated against a realistic fixture, no binary needed.
The fixture mirrors what EnergyPlus 22.1 actually writes (standalone heading
with a trailing blank line, indented data rows starting with an empty cell,
energy in GJ), which the previous parser tripped on — it matched headings with
substring and reset table state on blank lines, so zero rows were ever
collected from real output."""
import math

from energy_modeler.parser.results import parse_run

# Mirrors EnergyPlus 22.1 eplustbl.csv:
#  - REPORT: marker, FOR:/Building: top-level fields,
#  - 'End Uses' standalone heading followed by a blank line,
#  - indented column header (',,Electricity [GJ],...') and data rows
#    ('  ,Heating,...'),
#  - End Uses By Subcategory follows immediately to catch the substring trap.
EPLUSTBL_GJ = """Program Version:,EnergyPlus, Version 22.1.0-ed759b17ee
Tabular Output Report in Format: ,Comma

Building:,OfficeMedium

REPORT:,Annual Building Utility Performance Summary
FOR:,Entire Facility

End Uses

,,Electricity [GJ],Natural Gas [GJ],Gasoline [GJ],Diesel [GJ],Coal [GJ],Fuel Oil No 1 [GJ],Fuel Oil No 2 [GJ],Propane [GJ],Other Fuel 1 [GJ],Other Fuel 2 [GJ],District Cooling [GJ],District Heating [GJ],Water [m3]
,Heating,50.000,6.000,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
,Cooling,290.000,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
,Interior Lighting,162.000,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
,Interior Equipment,366.000,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
,Fans,90.000,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
,Total End Uses,958.000,6.000,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0

End Uses By Subcategory

,,Subcategory,Electricity [GJ]
,Heating,General,50.000
"""

# 1 GJ = 277.7777... kWh
G = 277.7778


def _close(actual: float, expected: float, tol: float = 0.5) -> bool:
    return math.isclose(actual, expected, abs_tol=tol)


def test_parse_run_from_eplustbl(tmp_path):
    (tmp_path / "eplustbl.csv").write_text(EPLUSTBL_GJ)
    rr = parse_run(tmp_path, "baseline", station="TAMPA INTL AP")

    assert rr.engine_mode == "energyplus"
    eu = rr.annual_end_uses
    # GJ -> kWh conversion applied per-row.
    assert _close(eu.heating_elec_kwh, 50 * G)
    assert _close(eu.cooling_elec_kwh, 290 * G)
    assert _close(eu.interior_lighting_kwh, 162 * G)
    assert _close(eu.interior_equipment_kwh, 366 * G)
    assert _close(eu.fans_kwh, 90 * G)
    assert _close(eu.total_electricity_kwh, 958 * G)
    assert _close(eu.heating_gas_kwh, 6 * G)
    assert rr.peak_demand.cooling_peak_kw > 0


def test_parse_run_kwh_header_skips_conversion(tmp_path):
    """When the eplustbl header reads [kWh] (OutputControl:Table:Style JtoKWH),
    parse_annual_end_uses must NOT also multiply by 277.78."""
    fixture = """REPORT:,Annual Building Utility Performance Summary
FOR:,Entire Facility

End Uses

,,Electricity [kWh],Natural Gas [kWh],Gasoline [kWh]
,Cooling,12345.6,0.0,0.0
"""
    (tmp_path / "eplustbl.csv").write_text(fixture)
    rr = parse_run(tmp_path, "baseline")
    assert _close(rr.annual_end_uses.cooling_elec_kwh, 12345.6)


def test_parse_run_substring_heading_does_not_reopen_table(tmp_path):
    """'End Uses By Subcategory' must not be matched as 'End Uses' (substring),
    otherwise its rows leak into the result and corrupt the totals."""
    fixture = """REPORT:,Annual Building Utility Performance Summary
FOR:,Entire Facility

End Uses

,,Electricity [GJ]
,Cooling,100.0

End Uses By Subcategory

,,Subcategory,Electricity [GJ]
,Cooling,General,99.0
"""
    (tmp_path / "eplustbl.csv").write_text(fixture)
    rr = parse_run(tmp_path, "baseline")
    # Only the 100 GJ Cooling row counts — the Subcategory 99 GJ must not.
    assert _close(rr.annual_end_uses.cooling_elec_kwh, 100 * G)

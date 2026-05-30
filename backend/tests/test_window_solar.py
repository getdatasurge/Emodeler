"""Per-window transmitted-solar parser: eplusout.csv column shape is
'<key>:Surface Window Transmitted Solar Radiation Energy [J](<freq>)'.
The parser sums monthly Joules per surface and converts to kWh. The aggregator
in parser_bridge then maps each prototype window's Name token (South / North
/ East / West) to a cardinal-direction bar for the dashboard."""
import math
from pathlib import Path

import pytest

from energy_modeler.engine.parser_bridge import _attach_window_solar
from energy_modeler.parser.eplus_window_solar import (
    J_TO_KWH,
    parse_window_transmitted_solar,
)
from energy_modeler.schemas import EnergyEndUses, PeakDemand, RunResult

EPLUSOUT_FIXTURE = (
    'Date/Time,'
    'Perimeter_bot_ZN_1_Wall_South_Window1:Surface Window Transmitted Solar Radiation Energy [J](Monthly),'
    'Perimeter_bot_ZN_1_Wall_South_Window2:Surface Window Transmitted Solar Radiation Energy [J](Monthly),'
    'Perimeter_bot_ZN_3_Wall_West_Window1:Surface Window Transmitted Solar Radiation Energy [J](Monthly),'
    'Some Random Variable [W](Hourly)\n'
    # 3 months of values (enough to cover the annual sum logic). Random,
    # unrelated column at the end is ignored by the regex.
    '01/01  24:00,1000000000,500000000,800000000,12.3\n'
    '02/01  24:00,1500000000,400000000,900000000,11.0\n'
    '03/01  24:00,2000000000,300000000,1100000000,10.4\n'
)


def _run() -> RunResult:
    return RunResult(
        run_id="r", scenario_label="x", engine_mode="energyplus",
        energyplus_version="22.1.0", weather_station="TPA",
        weather_dataset="TMY3",
        annual_end_uses=EnergyEndUses(),
        peak_demand=PeakDemand(),
        windows=[], monthly_cooling_kwh=[], warnings=[],
    )


def test_parse_window_transmitted_solar_sums_monthly_joules_to_kwh(tmp_path: Path):
    (tmp_path / "eplusout.csv").write_text(EPLUSOUT_FIXTURE)
    out = parse_window_transmitted_solar(tmp_path)
    # South Window1: 1.0e9 + 1.5e9 + 2.0e9 = 4.5e9 J -> 4.5e9 / 3.6e6 = 1250 kWh
    assert math.isclose(out["Perimeter_bot_ZN_1_Wall_South_Window1"], 4.5e9 * J_TO_KWH, abs_tol=0.5)
    # South Window2: 0.5 + 0.4 + 0.3 = 1.2e9 J -> 333.3 kWh
    assert math.isclose(out["Perimeter_bot_ZN_1_Wall_South_Window2"], 1.2e9 * J_TO_KWH, abs_tol=0.5)
    # West Window1: 0.8 + 0.9 + 1.1 = 2.8e9 J -> 777.8 kWh
    assert math.isclose(out["Perimeter_bot_ZN_3_Wall_West_Window1"], 2.8e9 * J_TO_KWH, abs_tol=0.5)
    # The unrelated Hourly variable must NOT appear in the result.
    assert "Some Random Variable" not in str(out)
    # Three matching columns parsed, no spurious entries.
    assert len(out) == 3


def test_parse_missing_file_returns_empty_dict(tmp_path: Path):
    assert parse_window_transmitted_solar(tmp_path) == {}


def test_parse_csv_without_matching_column_returns_empty_dict(tmp_path: Path):
    (tmp_path / "eplusout.csv").write_text(
        "Date/Time,Zone Mean Air Temperature [C](Hourly)\n"
        "01/01  01:00,23.4\n"
    )
    assert parse_window_transmitted_solar(tmp_path) == {}


def test_attach_window_solar_aggregates_per_cardinal_orientation(tmp_path: Path):
    (tmp_path / "eplusout.csv").write_text(EPLUSOUT_FIXTURE)
    rr = _run()
    _attach_window_solar(rr, tmp_path, scale=1.0)
    by_name = {w.surface_name: w for w in rr.windows}
    # Two South windows aggregate into one bucket; West has its own.
    expected_south = (4.5e9 + 1.2e9) * J_TO_KWH
    expected_west = 2.8e9 * J_TO_KWH
    assert "Face_S_total" in by_name
    assert math.isclose(by_name["Face_S_total"].annual_solar_transmitted_kwh, expected_south, abs_tol=0.5)
    assert math.isclose(by_name["Face_W_total"].annual_solar_transmitted_kwh, expected_west, abs_tol=0.5)
    # Surface name layout matches the chart's split('_')[1] orientation key.
    for w in rr.windows:
        assert w.surface_name.startswith("Face_")
        assert w.surface_name.split("_")[1] in {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "H", "?"}


def test_attach_window_solar_noop_without_csv(tmp_path: Path):
    rr = _run()
    _attach_window_solar(rr, tmp_path, scale=1.0)
    assert rr.windows == []


def test_attach_window_solar_unparseable_name_lands_in_question_bucket(tmp_path: Path):
    (tmp_path / "eplusout.csv").write_text(
        'Date/Time,'
        'Anonymous_Skylight:Surface Window Transmitted Solar Radiation Energy [J](Monthly)\n'
        '01/01  24:00,3600000000\n'  # 1000 kWh
    )
    rr = _run()
    _attach_window_solar(rr, tmp_path, scale=1.0)
    # No North/South/East/West token in the name -> '?' bucket so it's
    # visible in the audit even if it can't be assigned to a chart bar.
    assert any(w.surface_name == "Face_?_total" for w in rr.windows)
    assert pytest.approx(rr.windows[0].annual_solar_transmitted_kwh, abs=1.0) == 1000.0

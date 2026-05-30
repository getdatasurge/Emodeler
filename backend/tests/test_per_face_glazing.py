"""Per-face base glazing: a project with mixed glass (tinted south, clear
elsewhere) must NOT be collapsed to a single construction shared by every
window. parser_bridge._glazings_by_cardinal builds the per-cardinal mapping,
idf_builder.build_scenario_idf detects it, and idf_ops.set_window_construction_by_orientation
dispatches each prototype window to its elevation's construction."""
import types

from energy_modeler.engine import idf_ops
from energy_modeler.engine.inputs import EngineFace, EngineProject
from energy_modeler.engine.parser_bridge import _glazings_by_cardinal


def _project(faces: list[EngineFace]) -> EngineProject:
    return EngineProject(
        project_id="x", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540",
        utility_rate_usd_kwh=0.1145, egrid_subregion="FRCC",
        faces=faces,
    )


def test_uniform_glazing_maps_all_cardinals_to_the_same_record():
    proj = _project([
        EngineFace("S", 800, "dbl_clear_3mm_13mmAir"),
        EngineFace("N", 800, "dbl_clear_3mm_13mmAir"),
        EngineFace("E", 800, "dbl_clear_3mm_13mmAir"),
        EngineFace("W", 800, "dbl_clear_3mm_13mmAir"),
    ])
    out = _glazings_by_cardinal(proj)
    assert set(out.keys()) == {"N", "E", "S", "W", "DEFAULT"}
    # All resolve to the same base-glazing record (same shgc).
    shgcs = {out[k]["shgc"] for k in out}
    assert len(shgcs) == 1


def test_mixed_glazing_picks_dominant_per_cardinal():
    # Tinted south (deliberately the heavier S area), clear everywhere else.
    proj = _project([
        EngineFace("S", 1000, "dbl_lowE_3mm_13mmAir"),
        EngineFace("SE", 500, "dbl_lowE_3mm_13mmAir"),
        EngineFace("E", 800, "dbl_clear_3mm_13mmAir"),
        EngineFace("N", 600, "dbl_clear_3mm_13mmAir"),
        EngineFace("W", 700, "dbl_clear_3mm_13mmAir"),
    ])
    out = _glazings_by_cardinal(proj)
    # S has 1000 sf tinted + 250 sf tinted from half of SE -> tinted wins.
    assert out["S"]["id"] == "dbl_lowE_3mm_13mmAir"
    # E has 800 sf clear + 250 sf tinted from half of SE -> clear wins.
    assert out["E"]["id"] == "dbl_clear_3mm_13mmAir"
    assert out["N"]["id"] == "dbl_clear_3mm_13mmAir"
    assert out["W"]["id"] == "dbl_clear_3mm_13mmAir"


def test_intercardinal_only_project_still_populates_all_cardinals():
    """If the user enters only SW (a single elevation), the parser still
    yields a glazing for every cardinal so unmatched-name windows don't
    fall through to the default fallback unintentionally."""
    proj = _project([EngineFace("SW", 1200, "dbl_clear_3mm_13mmAir")])
    out = _glazings_by_cardinal(proj)
    # S and W both inherit from the SW area, others fall back to the overall
    # dominant (which is also SW's glazing here).
    for c in ("N", "E", "S", "W"):
        assert out[c]["id"] == "dbl_clear_3mm_13mmAir"
    assert out["DEFAULT"]["id"] == "dbl_clear_3mm_13mmAir"


def _fake_window(name: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(Name=name, Surface_Type="Window", Construction_Name="orig")


def test_set_window_construction_by_orientation_dispatches_by_name_token():
    """Build a fake idf-like object whose FENESTRATIONSURFACE:DETAILED list
    has windows named like the DOE prototype (with 'South' / 'East' tokens),
    and verify each one ends up on the construction matching its elevation."""
    windows = [
        _fake_window("Perimeter_bot_ZN_1_Wall_South_Window1"),
        _fake_window("Perimeter_bot_ZN_3_Wall_East_Window2"),
        _fake_window("Perimeter_bot_ZN_4_Wall_North_Window1"),
        _fake_window("Some_Skylight_With_No_Direction"),
    ]
    fake_idf = types.SimpleNamespace(
        idfobjects={"FENESTRATIONSURFACE:DETAILED": windows, "WINDOW": []}
    )
    n = idf_ops.set_window_construction_by_orientation(
        fake_idf,
        {"S": "con_S", "E": "con_E", "N": "con_N", "W": "con_W", "DEFAULT": "con_DEF"},
    )
    assert n == 4
    assert windows[0].Construction_Name == "con_S"
    assert windows[1].Construction_Name == "con_E"
    assert windows[2].Construction_Name == "con_N"
    # The skylight had no direction token -> DEFAULT.
    assert windows[3].Construction_Name == "con_DEF"


def test_cardinal_from_name_handles_case_and_substring():
    assert idf_ops._cardinal_from_window_name("Wall_SOUTH_Window") == "S"
    assert idf_ops._cardinal_from_window_name("interior_north_door") == "N"
    assert idf_ops._cardinal_from_window_name("anonymous_glazing") is None
    assert idf_ops._cardinal_from_window_name("") is None

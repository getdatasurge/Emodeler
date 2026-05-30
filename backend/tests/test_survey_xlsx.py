"""Survey-sheet importer: read the 3M/IWFA workbook into engine Faces.

Fixtures are written in-test via openpyxl so the test mirrors what surveyors
deliver — header row, fill-down Compass (orientation written once per elevation,
windows listed beneath), blank rows between elevations, inches in W/H."""
from io import BytesIO

import pytest

openpyxl = pytest.importorskip("openpyxl")

from energy_modeler.parser.survey_xlsx import (  # noqa: E402
    GLASS_COLOR_TO_GLAZING_ID,
    collapse_to_single_project,
    group_by_building,
    parse_survey_xlsx,
)


def _make_workbook(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Survey Sheet"
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


HEADER = [
    "Building ID", "Floor #", "Map Number", "Zone", "Compromised?",
    "Inside/Outside", "Glass Color?", "Compass",
    "GC3200 Reading", "SG2700 Reading", "W", "H",
]


def test_aggregates_by_compass_and_converts_inches_to_sqft():
    rows = [
        HEADER,
        # SE elevation: three windows under one Compass marker (fill-down).
        ["Millstone Elementary", 1, 1, 1, None, "Outside", "Clear", "SE", None, None, 27, 20],
        [None, None, None, None, None, None, None, None, None, None, 30, 30],
        [None, None, None, None, None, None, None, None, None, None, 70, 30],
        # Blank row between elevations (must not break fill-down or aggregation).
        [None] * len(HEADER),
        # SW elevation: two windows.
        [None, None, 6, 2, None, None, None, "SW", None, None, 21, 20],
        [None, None, None, None, None, None, None, None, None, None, 16, 20],
        # NW elevation: one window.
        [None, None, 9, 1, None, None, None, "NW", None, None, 19, 24],
    ]
    rows_out = parse_survey_xlsx(_make_workbook(rows))
    by_o = {r.orientation: r for r in rows_out}

    # Three orientations land in the right order (engine PEAK_POA order).
    assert [r.orientation for r in rows_out] == ["SE", "SW", "NW"]

    # SE total = (27*20 + 30*30 + 70*30) sq in / 144 = (540 + 900 + 2100)/144 = 24.58 ft^2
    assert by_o["SE"].area_sqft == pytest.approx(24.58, abs=0.05)
    assert by_o["SE"].count == 3

    # SW total = (21*20 + 16*20) / 144 = 740/144 = 5.14 ft^2
    assert by_o["SW"].area_sqft == pytest.approx(5.14, abs=0.05)
    assert by_o["SW"].count == 2

    # NW = (19*24)/144 = 3.17 ft^2
    assert by_o["NW"].area_sqft == pytest.approx(3.17, abs=0.05)
    assert by_o["NW"].count == 1


def test_units_ft_skips_conversion():
    rows = [HEADER, [None]*7 + ["S", None, None, 10, 5]]
    out = parse_survey_xlsx(_make_workbook(rows), units="ft")
    # 10 ft * 5 ft = 50 sq ft (no /144).
    assert out[0].area_sqft == pytest.approx(50.0)


def test_skips_rows_with_missing_width_or_height_and_invalid_compass():
    rows = [
        HEADER,
        # Valid S row.
        [None]*7 + ["S", None, None, 24, 36],
        # Missing height -> skip.
        [None]*7 + ["S", None, None, 24, None],
        # Compass not in the 8-point set (e.g. 'SSW') -> skip.
        [None]*7 + ["SSW", None, None, 12, 12],
        # Blank Compass with no prior orientation -> skip.
    ]
    out = parse_survey_xlsx(_make_workbook(rows))
    assert len(out) == 1 and out[0].orientation == "S" and out[0].count == 1


def test_missing_required_column_raises():
    rows = [["Building ID", "Glass Color?", "Compass"]]  # no W / H
    with pytest.raises(ValueError, match="missing required column"):
        parse_survey_xlsx(_make_workbook(rows))


def test_glass_color_maps_to_tinted_base_glazings():
    rows = [
        HEADER,
        # Bronze SE windows.
        ["Building A", 1, 1, 1, None, "Outside", "Bronze", "SE", None, None, 30, 30],
        # Same elevation, same color (fills down), same building (fills down).
        [None, None, None, None, None, None, None, None, None, None, 40, 40],
        # Switch to clear glass on the S elevation.
        [None, None, 2, 1, None, None, "Clear", "S", None, None, 24, 36],
        # Grey (American spelling 'Gray' should also resolve).
        [None, None, 3, 1, None, None, "Gray", "W", None, None, 20, 20],
    ]
    out = parse_survey_xlsx(_make_workbook(rows))
    by = {(r.orientation, r.base_glazing_id): r for r in out}
    assert by[("SE", "dbl_bronze_3mm_13mmAir")].count == 2
    assert by[("S", "dbl_clear_3mm_13mmAir")].count == 1
    assert by[("W", "dbl_grey_3mm_13mmAir")].count == 1
    # Every catalog color resolves to a real entry id (no typos in the map).
    assert all(v.startswith("dbl_") for v in GLASS_COLOR_TO_GLAZING_ID.values())


def test_building_dimension_keeps_rows_separate_until_grouped():
    rows = [
        HEADER,
        ["Millstone Elementary", 1, 1, 1, None, None, "Clear", "S", None, None, 30, 30],
        # Second building, same orientation + glazing -> separate bucket pre-grouping.
        ["New Brunswick Middle", 1, 1, 1, None, None, "Clear", "S", None, None, 30, 30],
    ]
    out = parse_survey_xlsx(_make_workbook(rows))
    assert len(out) == 2
    assert {r.building_id for r in out} == {"Millstone Elementary", "New Brunswick Middle"}
    grouped = group_by_building(out)
    assert set(grouped.keys()) == {"Millstone Elementary", "New Brunswick Middle"}
    assert all(len(v) == 1 for v in grouped.values())


def test_collapse_merges_buildings_and_dedupes_notes():
    rows = [
        HEADER,
        ["Bldg A", 1, 1, 1, None, None, "Clear", "S", None, None, 30, 30],
        ["Bldg B", 2, 5, 2, None, None, "Clear", "S", None, None, 40, 40],
    ]
    out = parse_survey_xlsx(_make_workbook(rows))
    assert len(out) == 2  # two buildings, same orientation
    collapsed = collapse_to_single_project(out)
    assert len(collapsed) == 1  # single (S, clear) face after collapse
    face = collapsed[0]
    assert face.orientation == "S" and face.base_glazing_id == "dbl_clear_3mm_13mmAir"
    # Area is the sum of both buildings.
    assert face.area_sqft == pytest.approx((30 * 30 + 40 * 40) / 144.0, abs=0.05)
    # Notes carry the building list.
    assert face.notes is not None
    assert "Bldg A" in face.notes and "Bldg B" in face.notes


def test_notes_capture_floor_map_zone_for_audit_trail():
    rows = [
        HEADER,
        [None, 1, 1, 1, None, None, "Clear", "S", None, None, 30, 30],
        [None, 1, 3, 1, None, None, None,    None, None, None, 40, 30],
        [None, 2, 6, 2, None, None, None,    None, None, None, 20, 20],
    ]
    out = parse_survey_xlsx(_make_workbook(rows))
    assert len(out) == 1
    face = out[0]
    # 3 distinct floor / map / zone values get recorded for the bucket.
    assert face.notes is not None
    assert "Floors: 1, 2" in face.notes
    assert "Maps: 1, 3, 6" in face.notes
    assert "Zones: 1, 2" in face.notes


def test_resolves_sheet_when_renamed():
    wb = openpyxl.Workbook()
    wb.active.title = "Window Survey"  # not exactly 'Survey Sheet'
    ws = wb["Window Survey"]
    for row in [HEADER, [None]*7 + ["W", None, None, 36, 36]]:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    out = parse_survey_xlsx(buf.getvalue())
    assert out[0].orientation == "W" and out[0].area_sqft == pytest.approx(9.0)

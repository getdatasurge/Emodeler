"""Survey-sheet importer: read the 3M/IWFA workbook into engine Faces.

Fixtures are written in-test via openpyxl so the test mirrors what surveyors
deliver — header row, fill-down Compass (orientation written once per elevation,
windows listed beneath), blank rows between elevations, inches in W/H."""
from io import BytesIO

import pytest

openpyxl = pytest.importorskip("openpyxl")

from energy_modeler.parser.survey_xlsx import parse_survey_xlsx  # noqa: E402


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

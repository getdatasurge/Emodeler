"""Excel survey-sheet importer (spec Ch 10 / surveyor workflow).

Reads the IWFA-style window survey workbook used in the field — the same sheet
3M dealers exchange with their PMs — and aggregates rows by 8-point compass
orientation into Face inputs the engine consumes. Each row in the 'Survey Sheet'
tab is one window; the W/H columns are inches, Compass is one of N/NE/E/SE/S/
SW/W/NW (the workbook's bundled Lists tab pins the allowed values)."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

# Width/Height are recorded in inches on the IWFA survey sheet; convert to ft^2.
IN2_PER_FT2 = 144.0

VALID_COMPASS = {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "H"}

# Header tokens we resolve to column indices. The header row in the live sheet
# uses these exact labels ('Survey Sheet' tab, row 1).
_HEADER_ALIASES = {
    "compass": ("compass",),
    "width": ("w", "width", "width (in)", "w (in)"),
    "height": ("h", "height", "height (in)", "h (in)"),
    "glass_color": ("glass color?", "glass color", "color"),
}


@dataclass
class SurveyImportRow:
    """One aggregated face — orientation × base glazing, after summing W*H."""
    orientation: str
    area_sqft: float
    count: int
    base_glazing_id: str
    notes: str | None = None


def _norm(s: Any) -> str:
    return str(s).strip().lower() if s is not None else ""


def _find_columns(header: list[Any]) -> dict[str, int]:
    norm = [_norm(c) for c in header]
    out: dict[str, int] = {}
    for key, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                out[key] = norm.index(alias)
                break
    missing = [k for k in ("compass", "width", "height") if k not in out]
    if missing:
        raise ValueError(
            f"Survey sheet is missing required column(s): {missing}. "
            f"Saw headers: {[h for h in header if h is not None]}"
        )
    return out


def _to_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None


def parse_survey_xlsx(
    content: bytes,
    *,
    sheet_name: str = "Survey Sheet",
    default_base_glazing_id: str = "dbl_clear_3mm_13mmAir",
    units: str = "in",
) -> list[SurveyImportRow]:
    """Parse a 3M/IWFA survey workbook and return one SurveyImportRow per
    (orientation × base_glazing_id) bucket, with summed area and window count.

    The W/H columns are inches by default; pass `units="ft"` to skip the in->ft
    conversion. Blank Compass cells inherit from the most recent populated row
    (the live sheet fills down — surveyors write the orientation once per
    elevation, then list the windows beneath it)."""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required to import survey sheets") from exc

    wb = load_workbook(BytesIO(content), data_only=True, read_only=True)
    if sheet_name not in wb.sheetnames:
        # Be lenient: surveyors sometimes rename the tab.
        candidates = [n for n in wb.sheetnames if "survey" in n.lower()]
        if not candidates:
            raise ValueError(
                f"Workbook has no sheet matching 'Survey Sheet' (found: {wb.sheetnames})"
            )
        sheet_name = candidates[0]
    ws = wb[sheet_name]

    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if header is None:
        return []
    cols = _find_columns(list(header))
    factor = 1.0 if units == "ft" else 1.0 / IN2_PER_FT2

    last_compass = ""
    # bucket key -> [area_sum_sqft, window_count]
    buckets: dict[str, list[float]] = {}
    for raw in rows_iter:
        if raw is None or not any(c not in (None, "") for c in raw):
            continue
        compass = _norm(raw[cols["compass"]]).upper() if cols["compass"] < len(raw) else ""
        if compass:
            last_compass = compass
        compass = compass or last_compass
        if compass not in VALID_COMPASS:
            continue

        w = _to_float(raw[cols["width"]]) if cols["width"] < len(raw) else None
        h = _to_float(raw[cols["height"]]) if cols["height"] < len(raw) else None
        if not w or not h:
            continue
        area_sqft = w * h * factor

        bucket = buckets.setdefault(compass, [0.0, 0])
        bucket[0] += area_sqft
        bucket[1] += 1

    # Stable orientation order (matches the engine's PEAK_POA table).
    order = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "H"]
    return [
        SurveyImportRow(
            orientation=o,
            area_sqft=round(buckets[o][0], 2),
            count=int(buckets[o][1]),
            base_glazing_id=default_base_glazing_id,
            notes=None,
        )
        for o in order if o in buckets
    ]

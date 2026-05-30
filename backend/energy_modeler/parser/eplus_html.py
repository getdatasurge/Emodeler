"""Parse eplustbl.csv (the comma-separated tabular summary EnergyPlus writes
when OutputControl:Table:Style includes Comma) for annual end-use totals
(spec Ch 6.2). Used by the real EnergyPlus path."""
from __future__ import annotations

import csv
from pathlib import Path

# EnergyPlus reports tabular energy in GJ by default ("Tabular Output Report in
# Format" header confirms units); the engine and UI assume kWh. If a project
# enables OutputControl:Table:Style with JtoKWH the header reads [kWh] and we
# skip the conversion.
GJ_TO_KWH = 277.7778


def _f(val: str) -> float:
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _extract_table(
    csv_path: Path, report: str, table: str
) -> tuple[list[str], list[list[str]]]:
    """Return (column_header_row, data_rows) for one named table within a named
    report in eplustbl.csv.

    EnergyPlus 22.1 eplustbl.csv structure::

        REPORT:,Annual Building Utility Performance Summary
        FOR:,Entire Facility
        Values gathered over   8760.00 hours

        End Uses                               <- standalone heading (no commas)
                                                <- blank line, must NOT reset state
        ,,Electricity [GJ],Natural Gas [GJ],...,Water [m3]
        ,Heating,1460.18,17.87,0.00,...
        ,Cooling,87.64,0.00,0.00,...
        ...

        End Uses By Subcategory                <- next heading ends this block

    Two issues the previous implementation tripped on:

    * The blank line between the heading and the data was treated as a table
      terminator, so we never collected the indented rows.
    * Headings were matched with ``in``, so 'End Uses By Subcategory' would
      re-open the 'End Uses' table. We now require an exact (case- and
      space-insensitive) match.
    """
    header: list[str] = []
    data: list[list[str]] = []
    if not csv_path.exists():
        return header, data
    target_report = report.lower().replace(" ", "")
    target_table = table.lower().replace(" ", "")
    in_report = False
    in_table = False
    with csv_path.open(newline="") as fh:
        for raw in csv.reader(fh):
            if not raw or not any(c.strip() for c in raw):
                continue  # blank line — keep state as-is
            first = raw[0].strip()
            if first.upper().startswith("REPORT:"):
                joined = ",".join(raw).lower().replace(" ", "")
                in_report = target_report in joined
                in_table = False
                continue
            if not in_report:
                continue
            if first:
                # Top-level marker like 'FOR:', 'Building:', 'Environment:'.
                if first.endswith(":"):
                    continue
                # Standalone heading row — enter the target table only on an
                # exact match, otherwise leave (or stay outside) the table.
                in_table = first.lower().replace(" ", "") == target_table
                continue
            if not in_table:
                continue
            # raw[0] is empty -> indented row inside the table block. The first
            # one is the column header (raw[1] is empty); the rest are data
            # rows (raw[1] holds the end-use label).
            if not header:
                header = raw
            else:
                data.append(raw)
    return header, data


def parse_annual_end_uses(run_dir: Path) -> dict[str, dict[str, float]]:
    """End-use category (lowercase, underscored) -> annual energy by fuel, in kWh."""
    header, rows = _extract_table(
        run_dir / "eplustbl.csv",
        report="Annual Building Utility Performance Summary",
        table="End Uses",
    )
    factor = GJ_TO_KWH if any("[GJ]" in c for c in header) else 1.0
    result: dict[str, dict[str, float]] = {}
    for row in rows:
        # Drop the leading-empty indent so row[0] is the end-use label, row[1]
        # is electricity, row[2] is gas, ... matching the header order.
        if row and not row[0].strip():
            row = row[1:]
        if len(row) < 2:
            continue
        end_use = row[0].strip().lower().replace(" ", "_")

        def col(i: int, _row: list[str] = row) -> float:
            return _f(_row[i]) * factor if i < len(_row) else 0.0

        result[end_use] = {
            "electricity_kwh": col(1),
            "gas_kwh": col(2),
            "district_cool_kwh": col(11),
            "district_heat_kwh": col(12),
        }
    return result

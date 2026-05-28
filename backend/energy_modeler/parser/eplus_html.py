"""Parse eplustbl.csv (the CSV mirror of the HTML summary tables) for annual
end-use totals (spec Ch 6.2). Used by the real EnergyPlus path."""
from __future__ import annotations

import csv
from pathlib import Path


def _f(val: str) -> float:
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _extract_table(csv_path: Path, report: str, table: str) -> list[list[str]]:
    """Return the rows of a named table within a named report from eplustbl.csv.

    EnergyPlus writes a flat CSV where 'REPORT:,<name>' and 'For:,<table>' marker
    rows delimit each block. We collect the data rows that follow the header."""
    rows: list[list[str]] = []
    if not csv_path.exists():
        return rows
    in_report = in_table = False
    with csv_path.open(newline="") as fh:
        for raw in csv.reader(fh):
            if not raw:
                in_table = False
                continue
            first = raw[0].strip()
            if first.upper().startswith("REPORT:"):
                # EnergyPlus writes the title with spaces ("Annual Building
                # Utility Performance Summary"); match space-insensitively.
                joined = ",".join(raw).lower().replace(" ", "")
                in_report = report.lower().replace(" ", "") in joined
                in_table = False
                continue
            if in_report and (
                first == table
                or table.lower().replace(" ", "") in first.lower().replace(" ", "")
            ):
                in_table = True
                continue
            if in_report and in_table and first and not first.endswith(":"):
                rows.append(raw)
    return rows


def parse_annual_end_uses(run_dir: Path) -> dict[str, dict[str, float]]:
    """Dict keyed by end-use category with annual kWh by fuel."""
    table = _extract_table(
        run_dir / "eplustbl.csv",
        report="AnnualBuildingUtilityPerformanceSummary",
        table="End Uses",
    )
    result: dict[str, dict[str, float]] = {}
    for row in table:
        if len(row) < 5:
            continue
        end_use = row[0].strip().lower().replace(" ", "_")
        result[end_use] = {
            "electricity_kwh": _f(row[1]),
            "gas_kwh": _f(row[2]),
            "district_heat_kwh": _f(row[3]),
            "district_cool_kwh": _f(row[4]),
        }
    return result

"""Parse per-window 'Surface Window Transmitted Solar Radiation Energy' out
of eplusout.csv (the variable CSV EnergyPlus writes when Output:Variable is
requested). Feeds the 'Solar gain rejected by face' chart by aggregating
per-window energy to per-orientation kWh."""
from __future__ import annotations

import csv
import re
from pathlib import Path

# 1 kWh = 3.6 MJ; eplusout.csv reports Energy variables in joules.
J_TO_KWH = 1.0 / 3_600_000.0

# Header column shape EnergyPlus writes for an Output:Variable on a key, e.g.
#   "Perimeter_bot_ZN_1_Wall_South_Window1:Surface Window Transmitted Solar
#    Radiation Energy [J](Monthly)"
_VAR = "Surface Window Transmitted Solar Radiation Energy"
_HEADER_RE = re.compile(
    rf"^(?P<key>[^:]+):\s*{re.escape(_VAR)}\s*\[",
    re.IGNORECASE,
)


def parse_window_transmitted_solar(run_dir: Path) -> dict[str, float]:
    """Return {window_surface_name: annual_kWh_transmitted_solar}.

    Sums whatever rows EnergyPlus wrote — monthly (12 rows) is what we ask
    for in add_standard_outputs, but the function is frequency-agnostic so
    a higher-frequency run still aggregates correctly to annual. Missing
    file -> empty dict (the caller leaves windows=[] and the chart hides).
    """
    csv_path = run_dir / "eplusout.csv"
    if not csv_path.exists():
        return {}
    with csv_path.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            return {}
        # Pre-match the columns we care about once.
        matched: list[tuple[int, str]] = []
        for idx, col in enumerate(header):
            m = _HEADER_RE.match(col.strip())
            if m:
                matched.append((idx, m.group("key").strip()))
        if not matched:
            return {}
        totals_j: dict[str, float] = {key: 0.0 for _, key in matched}
        for row in reader:
            for idx, key in matched:
                if idx >= len(row):
                    continue
                cell = row[idx].strip()
                if not cell:
                    continue
                try:
                    totals_j[key] += float(cell)
                except ValueError:
                    pass
    return {key: round(j * J_TO_KWH, 1) for key, j in totals_j.items()}

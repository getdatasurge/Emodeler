"""LEED EAc Optimize Energy Performance (spec Ch 6.6).

PCI per ASHRAE 90.1-2016 Appendix G Section 4.2.1.1; point thresholds per LEED
v4.1 BD+C EAc. The Appendix G baseline cost (denominator) comes from the
EnergyPlus baseline run (engine/appendix_g.py); these helpers compute the index
and points from proposed vs. baseline cost and are unit-tested independently.
"""
from __future__ import annotations

import csv
from functools import lru_cache

from .config import DATA_DIR

_DEFAULT_PCIT = 0.65


@lru_cache(maxsize=1)
def _pci_targets() -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    path = DATA_DIR / "pci_targets.csv"
    if not path.exists():
        return out
    with path.open() as fh:
        for row in csv.DictReader(line for line in fh if not line.startswith("#")):
            try:
                out[(row["building_type"], row["climate_zone"])] = float(row["pcit"])
            except (KeyError, ValueError):
                continue
    return out


def performance_cost_index(proposed_total_cost: float, baseline_total_cost: float) -> float:
    """PCI = Proposed Building Performance / Baseline Building Performance."""
    if baseline_total_cost <= 0:
        return float("nan")
    return proposed_total_cost / baseline_total_cost


def pci_target(building_type: str, climate_zone: str, standard: str = "90.1-2016") -> float:
    """PCIt per Standard 90.1-2016 Appendix G Table 4.2.1.1, from
    data/pci_targets.csv. Falls back to a representative office target.

    NOTE: the bundled CSV holds representative placeholders — verify against the
    official LEED v4.1 table before relying on a point count for a submission."""
    targets = _pci_targets()
    return (
        targets.get((building_type, climate_zone))
        or targets.get((building_type, "*"))
        or _DEFAULT_PCIT
    )


def leed_points_v41(pci: float, target: float, delta_ghg_pct: float) -> tuple[int, int]:
    """(cost_points, ghg_points) per LEED v4.1 BD+C EAc — up to 9 + 9 = 18.

    Cost points scale with improvement of PCI below target; GHG points scale
    with the GHG-metric improvement. Both clamped to [0, 9].
    """
    if pci <= 0 or target <= 0:
        return (0, 0)
    cost_improvement_pct = max(0.0, (target - pci) / target * 100.0)
    cost_points = min(9, int(cost_improvement_pct // 6))  # ~6%/point, capped
    ghg_points = min(9, max(0, int(delta_ghg_pct // 6)))
    return (cost_points, ghg_points)

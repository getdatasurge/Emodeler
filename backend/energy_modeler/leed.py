"""LEED EAc Optimize Energy Performance (spec Ch 6.6).

Phase 3 feature. PCI per ASHRAE 90.1-2016 Appendix G Section 4.2.1.1; point
thresholds per LEED v4.1 BD+C EAc. The Appendix G baseline IDF generation is
itself deferred to Phase 3 (engine/appendix_g.py is a stub), so these helpers
are exercised by unit tests but not yet wired into the default calc pipeline.
"""
from __future__ import annotations


def performance_cost_index(proposed_total_cost: float, baseline_total_cost: float) -> float:
    """PCI = Proposed Building Performance / Baseline Building Performance."""
    if baseline_total_cost <= 0:
        return float("nan")
    return proposed_total_cost / baseline_total_cost


def pci_target(building_type: str, climate_zone: str, standard: str = "90.1-2016") -> float:
    """PCIt per Standard 90.1-2016 Appendix G Table 4.2.1.1.

    Phase 1 placeholder: the full per-(building-type x climate-zone) table ships
    in Phase 3 (data/pci_targets.csv). 0.65 is a representative office target.
    """
    return 0.65


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

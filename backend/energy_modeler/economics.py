"""Economics — payback, NPV, IRR (spec Ch 6.4).

Default assumptions (all user-overridable per project):
  - Film useful life: 15 yr (3M Prestige commercial warranty)
  - Discount rate: 5.0% (municipal / school-district capital planning)
  - Utility rate escalation: 2.5%/yr (EIA AEO reference case)
"""
from __future__ import annotations

import math

DEFAULT_LIFE_YRS = 15
DEFAULT_DISCOUNT = 0.05
DEFAULT_ESCALATION = 0.025


def simple_payback(project_cost: float, annual_savings: float) -> float:
    """Years to recover project cost. NaN if annual_savings <= 0."""
    if annual_savings <= 0:
        return float("nan")
    return project_cost / annual_savings


def npv(
    annual_savings: float,
    life_yrs: int,
    discount: float,
    project_cost: float,
    escalation: float = DEFAULT_ESCALATION,
) -> float:
    """NPV at the discount rate, with optional utility-rate escalation."""
    pv = -project_cost
    for t in range(1, life_yrs + 1):
        cash_t = annual_savings * ((1 + escalation) ** (t - 1))
        pv += cash_t / ((1 + discount) ** t)
    return pv


def irr(
    annual_savings: float,
    life_yrs: int,
    project_cost: float,
    escalation: float = DEFAULT_ESCALATION,
) -> float:
    """Bisection IRR — solve NPV(r) = 0. Returns NaN when no positive cash flow."""
    if annual_savings <= 0 or project_cost <= 0:
        return float("nan")
    lo, hi = -0.5, 1.0
    mid = (lo + hi) / 2
    for _ in range(80):
        mid = (lo + hi) / 2
        v = npv(annual_savings, life_yrs, mid, project_cost, escalation)
        if abs(v) < 0.01:
            return mid
        if v > 0:
            lo = mid
        else:
            hi = mid
    return mid


def percent(value: float) -> float:
    """Convert a rate (0.114) to a percentage (11.4), preserving NaN."""
    return value * 100.0 if not math.isnan(value) else float("nan")

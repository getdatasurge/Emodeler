import math

from energy_modeler import economics


def test_simple_payback():
    assert economics.simple_payback(10000, 2000) == 5.0
    assert math.isnan(economics.simple_payback(10000, 0))
    assert math.isnan(economics.simple_payback(10000, -50))


def test_npv_positive_when_savings_recover_cost():
    # $2000/yr for 15 yr at 5% discount, 2.5% escalation easily beats $10k cost.
    val = economics.npv(2000, 15, 0.05, 10000, 0.025)
    assert val > 0


def test_npv_negative_when_cost_too_high():
    assert economics.npv(500, 15, 0.05, 100000, 0.025) < 0


def test_irr_solves_npv_zero():
    rate = economics.irr(2000, 15, 10000, 0.025)
    # NPV at the solved IRR should be ~0.
    assert abs(economics.npv(2000, 15, rate, 10000, 0.025)) < 1.0


def test_irr_nan_when_no_savings():
    assert math.isnan(economics.irr(0, 15, 10000))


def test_percent_preserves_nan():
    assert economics.percent(0.114) == 11.4
    assert math.isnan(economics.percent(float("nan")))


def test_demand_savings():
    # 20 kW peak cut x 0.8 coincidence x $15/kW x 12 months.
    assert economics.annual_demand_savings(20.0, 15.0) == 20.0 * 0.8 * 15.0 * 12


def test_demand_savings_zero_without_rate_or_reduction():
    assert economics.annual_demand_savings(20.0, 0.0) == 0.0
    assert economics.annual_demand_savings(0.0, 15.0) == 0.0

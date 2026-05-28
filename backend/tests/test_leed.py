from energy_modeler import leed


def test_pci_ratio():
    assert leed.performance_cost_index(80, 100) == 0.8


def test_pci_nan_on_zero_baseline():
    import math

    assert math.isnan(leed.performance_cost_index(80, 0))


def test_points_clamped():
    cost, ghg = leed.leed_points_v41(pci=0.40, target=0.65, delta_ghg_pct=60)
    assert 0 <= cost <= 9
    assert 0 <= ghg <= 9


def test_no_points_when_pci_above_target():
    cost, ghg = leed.leed_points_v41(pci=0.70, target=0.65, delta_ghg_pct=0)
    assert cost == 0
    assert ghg == 0

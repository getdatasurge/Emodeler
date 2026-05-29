"""ASHRAE 90.1 Appendix G baseline spec lookups (spec Ch 5.5)."""
from energy_modeler.engine import appendix_g


def test_baseline_spec_hot_zone_caps_shgc():
    s = appendix_g.baseline_spec("MediumOffice", "2A", floors=3, area_sf=53000)
    assert s.window_shgc == 0.25  # hot zone -> hard SHGC cap
    assert s.window_u_factor == 0.50
    assert s.lpd_w_sf == 0.79
    assert "VAV" in s.hvac_system  # >=25k sf -> packaged VAV


def test_baseline_spec_cold_zone_relaxes_shgc():
    s = appendix_g.baseline_spec("SecondarySchool", "6A", floors=2, area_sf=200000)
    assert s.window_shgc == 0.40
    assert s.lpd_w_sf == 0.87


def test_baseline_system_scales_with_size():
    assert "PSZ" in appendix_g.baseline_system_type(1, 10_000)
    assert "Packaged VAV" in appendix_g.baseline_system_type(2, 50_000)
    assert "built-up" in appendix_g.baseline_system_type(8, 200_000)

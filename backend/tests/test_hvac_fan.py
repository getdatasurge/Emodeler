"""HVAC fan power override beyond COP. Reducing solar load via film cuts
fan work too — a defensible cooling-savings number needs fan kW/CFM right.
set_fan_kw_per_cfm scales each Fan:* object's Pressure_Rise to achieve the
target electrical power per CFM while preserving Fan_Total_Efficiency."""
import types

from energy_modeler.engine import idf_ops


def _fake_fan(eff: float = 0.65, pressure: float = 600.0) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        Fan_Total_Efficiency=eff, Pressure_Rise=pressure
    )


def _fake_idf(**fans) -> types.SimpleNamespace:
    """fans={'FAN:VARIABLEVOLUME': [...], 'FAN:ONOFF': [...]} etc."""
    base = {
        "FAN:VARIABLEVOLUME": [],
        "FAN:CONSTANTVOLUME": [],
        "FAN:ONOFF": [],
        "FAN:SYSTEMMODEL": [],
    }
    base.update(fans)
    return types.SimpleNamespace(idfobjects=base)


def test_set_fan_kw_per_cfm_scales_pressure_rise_to_match_target():
    """A 0.0005 kW/CFM target at 0.65 fan efficiency yields a known
    Pressure_Rise. Formula: Pa = (kW/CFM) * 1000 / 0.000471947 * efficiency."""
    fan = _fake_fan(eff=0.65, pressure=600.0)
    idf = _fake_idf()
    idf.idfobjects["FAN:VARIABLEVOLUME"] = [fan]
    n = idf_ops.set_fan_kw_per_cfm(idf, 0.0005)
    assert n == 1
    # target W/(m3/s) = 0.0005 * 1000 / 0.000471947 = 1059.32; * 0.65 = 688.6 Pa
    assert abs(fan.Pressure_Rise - 688.6) < 1.0


def test_set_fan_kw_per_cfm_touches_every_fan_class_present():
    fans_by_class = {
        "FAN:VARIABLEVOLUME": [_fake_fan(0.60, 500.0)],
        "FAN:CONSTANTVOLUME": [_fake_fan(0.55, 450.0)],
        "FAN:ONOFF": [_fake_fan(0.50, 300.0), _fake_fan(0.50, 350.0)],
    }
    idf = _fake_idf(**fans_by_class)
    n = idf_ops.set_fan_kw_per_cfm(idf, 0.001)  # 1 W/CFM
    assert n == 4
    # Each fan's Pressure_Rise scales with its OWN efficiency (preserves the
    # original eff value, only rewrites the pressure component).
    for cls, fans in fans_by_class.items():
        for fan in fans:
            expected = (0.001 * 1000.0 / 0.000471947) * fan.Fan_Total_Efficiency
            assert abs(fan.Pressure_Rise - expected) < 1.0, cls


def test_set_fan_kw_per_cfm_noop_when_value_missing_or_invalid():
    fan = _fake_fan(0.65, 600.0)
    idf = _fake_idf()
    idf.idfobjects["FAN:VARIABLEVOLUME"] = [fan]
    assert idf_ops.set_fan_kw_per_cfm(idf, None) == 0
    assert idf_ops.set_fan_kw_per_cfm(idf, 0) == 0
    assert idf_ops.set_fan_kw_per_cfm(idf, -0.001) == 0
    # Pressure_Rise untouched on no-op.
    assert fan.Pressure_Rise == 600.0


def test_set_fan_kw_per_cfm_handles_autosize_efficiency():
    """DOE prototypes often ship Fan_Total_Efficiency='Autosize' or empty.
    Helper falls back to 0.6 instead of blowing up."""
    fan = types.SimpleNamespace(Fan_Total_Efficiency="Autosize", Pressure_Rise=500.0)
    idf = _fake_idf()
    idf.idfobjects["FAN:VARIABLEVOLUME"] = [fan]
    n = idf_ops.set_fan_kw_per_cfm(idf, 0.0005)
    assert n == 1
    # Fallback efficiency 0.6 * 1059.32 = 635.6 Pa
    assert abs(fan.Pressure_Rise - 635.6) < 1.0


def test_set_fan_kw_per_cfm_uses_design_pressure_rise_for_fan_systemmodel():
    """Fan:SystemModel renamed the field to Design_Pressure_Rise; the helper
    falls through to that when Pressure_Rise isn't present."""
    fan = types.SimpleNamespace(
        Fan_Total_Efficiency=0.7, Design_Pressure_Rise=600.0
    )
    idf = _fake_idf()
    idf.idfobjects["FAN:SYSTEMMODEL"] = [fan]
    n = idf_ops.set_fan_kw_per_cfm(idf, 0.0005)
    assert n == 1
    expected = (0.0005 * 1000.0 / 0.000471947) * 0.7
    assert abs(fan.Design_Pressure_Rise - expected) < 1.0

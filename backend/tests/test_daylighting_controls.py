"""Opt-in Daylighting:Controls injector. Models the lighting penalty a low-VT
film causes on buildings whose prototype lacks daylighting — otherwise the
film's VT reduction has no electricity-lighting offset and savings are slightly
overstated. Defensive: skips zones it can't confidently place a reference
point in and never raises on IDD field mismatch."""
import types

from energy_modeler.engine import idf_ops


def _fake_idf(zones, surfaces, fens, existing_daylit=()):
    """Build a minimal fake idf with the four object classes the helper reads."""
    objects = {
        "ZONE": list(zones),
        "BUILDINGSURFACE:DETAILED": list(surfaces),
        "FENESTRATIONSURFACE:DETAILED": list(fens),
        "DAYLIGHTING:CONTROLS": list(existing_daylit),
        "DAYLIGHTING:REFERENCEPOINT": [],
    }

    def new(kind, **fields):
        obj = types.SimpleNamespace(**fields)
        # Some Daylighting:Controls fields are set by setattr() AFTER construction
        # so we initialize the slots we know the helper may touch.
        for slot in (
            "Daylighting_Reference_Point_1_Name",
            "Fraction_of_Zone_Controlled_by_Reference_Point_1",
            "Illuminance_Setpoint_at_Reference_Point_1",
        ):
            if not hasattr(obj, slot):
                setattr(obj, slot, None)
        objects.setdefault(kind, []).append(obj)
        return obj

    return types.SimpleNamespace(idfobjects=objects, newidfobject=new)


def _zone(name: str, *, x: float = 0.0, y: float = 0.0, z: float = 0.0):
    return types.SimpleNamespace(Name=name, X_Origin=x, Y_Origin=y, Z_Origin=z)


def _wall(name: str, zone: str):
    return types.SimpleNamespace(Name=name, Zone_Name=zone)


def _window(name: str, parent_wall: str, surface_type: str = "Window"):
    return types.SimpleNamespace(
        Name=name, Building_Surface_Name=parent_wall, Surface_Type=surface_type
    )


def test_adds_one_per_zone_with_windows_and_no_existing_controls():
    idf = _fake_idf(
        zones=[_zone("Perim_S", x=0, y=0), _zone("Perim_N", x=0, y=20)],
        surfaces=[_wall("Wall_S", "Perim_S"), _wall("Wall_N", "Perim_N")],
        fens=[_window("Win_S", "Wall_S"), _window("Win_N", "Wall_N")],
    )
    n = idf_ops.add_daylighting_controls(idf, illuminance_setpoint_lux=500.0)
    assert n == 2
    assert len(idf.idfobjects["DAYLIGHTING:CONTROLS"]) == 2
    assert len(idf.idfobjects["DAYLIGHTING:REFERENCEPOINT"]) == 2
    # Reference point lands at origin + (1.5, 1.5, 0.76).
    rp_s = next(
        rp for rp in idf.idfobjects["DAYLIGHTING:REFERENCEPOINT"]
        if rp.Zone_or_Space_Name == "Perim_S"
    )
    assert rp_s.XCoordinate_of_Reference_Point == 1.5
    assert rp_s.YCoordinate_of_Reference_Point == 1.5
    assert abs(rp_s.ZCoordinate_of_Reference_Point - 0.76) < 0.001


def test_skips_zones_without_windows():
    """A core zone with only an interior wall (no fenestration) shouldn't get
    a daylighting reference point — no daylight to harvest."""
    idf = _fake_idf(
        zones=[_zone("Core"), _zone("Perim_S")],
        surfaces=[_wall("Core_Wall", "Core"), _wall("Wall_S", "Perim_S")],
        fens=[_window("Win_S", "Wall_S")],
    )
    n = idf_ops.add_daylighting_controls(idf)
    assert n == 1
    [(ctrl,)] = [(c,) for c in idf.idfobjects["DAYLIGHTING:CONTROLS"]]
    assert ctrl.Zone_or_Space_Name == "Perim_S"


def test_skips_zones_that_already_have_daylighting_controls():
    """A prototype that ships daylighting on some zones should keep them as
    authored — the helper only fills in the gaps."""
    pre_existing = types.SimpleNamespace(Zone_or_Space_Name="Perim_S")
    idf = _fake_idf(
        zones=[_zone("Perim_S"), _zone("Perim_N")],
        surfaces=[_wall("Wall_S", "Perim_S"), _wall("Wall_N", "Perim_N")],
        fens=[_window("Win_S", "Wall_S"), _window("Win_N", "Wall_N")],
        existing_daylit=[pre_existing],
    )
    n = idf_ops.add_daylighting_controls(idf)
    assert n == 1  # only Perim_N
    new = [c for c in idf.idfobjects["DAYLIGHTING:CONTROLS"] if c is not pre_existing]
    assert len(new) == 1 and new[0].Zone_or_Space_Name == "Perim_N"


def test_door_class_fenestration_is_ignored():
    """Doors (Surface_Type 'Door') are NOT glazing — adding a daylighting
    reference because of a door would be wrong."""
    idf = _fake_idf(
        zones=[_zone("Perim_S")],
        surfaces=[_wall("Wall_S", "Perim_S")],
        fens=[_window("Door_S", "Wall_S", surface_type="Door")],
    )
    assert idf_ops.add_daylighting_controls(idf) == 0


def test_setpoint_kwarg_is_threaded_to_the_object():
    idf = _fake_idf(
        zones=[_zone("Perim_S")],
        surfaces=[_wall("Wall_S", "Perim_S")],
        fens=[_window("Win_S", "Wall_S")],
    )
    idf_ops.add_daylighting_controls(idf, illuminance_setpoint_lux=300.0)
    ctrl = idf.idfobjects["DAYLIGHTING:CONTROLS"][0]
    assert ctrl.Illuminance_Setpoint_at_Reference_Point_1 == 300.0
    assert ctrl.Fraction_of_Zone_Controlled_by_Reference_Point_1 == 1.0


def test_handles_missing_zone_origin_gracefully():
    """Some Zone objects ship without X/Y/Z_Origin set (eppy returns ''); the
    helper falls back to 0 instead of crashing."""
    zone_no_origin = types.SimpleNamespace(
        Name="Perim_S", X_Origin="", Y_Origin=None, Z_Origin="",
    )
    idf = _fake_idf(
        zones=[zone_no_origin],
        surfaces=[_wall("Wall_S", "Perim_S")],
        fens=[_window("Win_S", "Wall_S")],
    )
    n = idf_ops.add_daylighting_controls(idf)
    assert n == 1
    rp = idf.idfobjects["DAYLIGHTING:REFERENCEPOINT"][0]
    assert rp.XCoordinate_of_Reference_Point == 1.5  # 0 + 1.5

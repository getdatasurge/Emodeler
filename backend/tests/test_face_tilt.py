"""Per-face surface tilt: sloped glazing / atrium / clerestory geometry that
the 8-point compass alone cannot describe. The field rides through the API,
the ORM, the EngineProject -> ResolvedBuilding -> estimate window record, and
the audit so a 3M Prestige sloped-glass project documents what the run
assumed."""
from energy_modeler.engine import runner
from energy_modeler.engine.inputs import (
    EngineFace,
    EngineProject,
    EngineScenario,
)


def _project(tilt_deg: float | None) -> EngineProject:
    return EngineProject(
        project_id="tilt", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540", utility_rate_usd_kwh=0.1145,
        egrid_subregion="FRCC",
        faces=[
            EngineFace("S", 1000, "dbl_clear_3mm_13mmAir", tilt_deg=tilt_deg),
        ],
        scenarios=[EngineScenario("Good", "3M-PR40X", 25000)],
    )


def test_default_tilt_is_vertical_for_cardinal_orientations():
    """tilt_deg=None -> the orientation's default (90 deg for cardinals,
    0 deg for H) gets stamped on the WindowSurfaceResult."""
    _, baseline, _, _ = runner.run_project(_project(tilt_deg=None))
    assert baseline.windows
    assert all(w.tilt_deg == 90.0 for w in baseline.windows)


def test_user_supplied_tilt_overrides_orientation_default():
    """A user-specified tilt (e.g. 30 deg for an atrium roof) replaces the
    cardinal vertical default and shows up in the audit record."""
    _, baseline, _, _ = runner.run_project(_project(tilt_deg=30.0))
    assert baseline.windows
    assert all(w.tilt_deg == 30.0 for w in baseline.windows)


def test_face_in_schema_accepts_tilt_in_range():
    from app.schemas_api import FaceIn

    ok = FaceIn(
        orientation="S", area_sqft=100, base_glazing_id="dbl_clear_3mm_13mmAir",
        tilt_deg=45.0,
    )
    assert ok.tilt_deg == 45.0


def test_face_in_schema_rejects_out_of_range_tilt():
    import pytest
    from pydantic import ValidationError

    from app.schemas_api import FaceIn

    for bad in (-1.0, 91.0, 150.0):
        with pytest.raises(ValidationError):
            FaceIn(
                orientation="S", area_sqft=100,
                base_glazing_id="dbl_clear_3mm_13mmAir",
                tilt_deg=bad,
            )

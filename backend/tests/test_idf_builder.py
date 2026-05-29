"""Real EnergyPlus pipeline: clean fallback without prototypes, and structural
validation of the assembled scenario IDF (eppy, no binary)."""
import glob
import os
from io import StringIO

import pytest

from energy_modeler.engine import parser_bridge, prototype_loader
from energy_modeler.engine.inputs import EngineFace, EngineProject, EngineScenario


def _project():
    return EngineProject(
        project_id="x", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540", utility_rate_usd_kwh=0.1145,
        egrid_subregion="FRCC",
        faces=[EngineFace("S", 873, "dbl_clear_3mm_13mmAir")],
        scenarios=[EngineScenario("Good", "3M-PR40X", 20000)],
    )


def test_real_pipeline_raises_without_prototypes():
    # No bundled prototypes / IDD here -> PrototypeNotFound, which runner catches
    # and degrades to the labeled analytical estimate.
    with pytest.raises(prototype_loader.PrototypeNotFound):
        parser_bridge.run_real_pipeline(_project())


def _load_idf_class():
    import eppy
    from eppy.modeleditor import IDF

    idds = sorted(glob.glob(os.path.join(os.path.dirname(eppy.__file__), "resources", "iddfiles", "*.idd")))
    if not idds:
        return None
    try:
        IDF.setiddname(idds[-1])
    except Exception:
        pass
    return IDF


try:
    _IDF = _load_idf_class()
except Exception:
    _IDF = None


@pytest.mark.skipif(_IDF is None, reason="eppy/IDD unavailable (worker-only dependency)")
def test_build_scenario_idf_assembles_runnable_idf():
    from energy_modeler import datastore
    from energy_modeler.engine import building, idf_builder
    from energy_modeler.engine.film_catalog import resolve as resolve_film

    # Synthetic prototype: a window surface + a DX cooling coil to mutate.
    idf = _IDF(StringIO("Version,9.2;"))
    idf.newidfobject("COIL:COOLING:DX:SINGLESPEED", Name="DX")
    idf.newidfobject("FENESTRATIONSURFACE:DETAILED", Name="W1", Surface_Type="Window")

    proj = _project()
    bldg = building.resolve(proj, datastore.get_prototype("MediumOffice"))
    base_glazing = datastore.get_base_glazing("dbl_clear_3mm_13mmAir")  # dual pane
    idf_builder.build_scenario_idf(idf, base_glazing, resolve_film("3M-PR40X"), bldg, "Good")

    # Film glazing construction created and applied to the window.
    assert "Good_glazing" in [c.Name for c in idf.idfobjects["CONSTRUCTION"]]
    assert idf.idfobjects["FENESTRATIONSURFACE:DETAILED"][0].Construction_Name == "Good_glazing"
    # Dual-pane assembly -> outer + inner panes present.
    mats = [m.Name for m in idf.idfobjects["WINDOWMATERIAL:GLAZING"]]
    assert "Good_glazing_outer" in mats and "Good_glazing_inner" in mats
    # As-built COP pinned, parser outputs added.
    assert float(idf.idfobjects["COIL:COOLING:DX:SINGLESPEED"][0].Gross_Rated_Cooling_COP) == bldg.cooling_cop
    assert len(idf.idfobjects["OUTPUT:METER"]) >= 5

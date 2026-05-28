"""eppy IDF-mutation primitives, validated against a synthetic IDF.

eppy is a worker-image dependency, so these skip where it isn't installed
(e.g. the slim CI/API env). The real DOE-prototype + binary validation is the
@eplus fixture suite (spec Ch 12)."""
import glob
import os
from io import StringIO

import pytest


def _load_idf_class():
    import eppy
    from eppy.modeleditor import IDF

    idds = sorted(glob.glob(os.path.join(os.path.dirname(eppy.__file__), "resources", "iddfiles", "*.idd")))
    if not idds:
        return None
    try:
        IDF.setiddname(idds[-1])
    except Exception:
        pass  # IDD already set for this process
    return IDF


try:
    _IDF = _load_idf_class()
except Exception:
    _IDF = None


@pytest.mark.skipif(_IDF is None, reason="eppy/IDD unavailable (worker-only dependency)")
def test_idf_mutation_primitives():
    from energy_modeler.engine import idf_ops

    idf = _IDF(StringIO("Version,9.2;"))
    coil = idf.newidfobject("COIL:COOLING:DX:SINGLESPEED", Name="DXCoil")
    win = idf.newidfobject("FENESTRATIONSURFACE:DETAILED", Name="W1", Surface_Type="Window")
    idf.newidfobject("CONSTRUCTION", Name="FilmConstruction")

    # COP override pins the rated COP (retrofit rule: fixed across scenarios).
    assert idf_ops.set_cooling_cop(idf, 2.5) == 1
    assert float(coil.Gross_Rated_Cooling_COP) == 2.5

    # Window construction swap is how a film is applied.
    assert idf_ops.set_window_construction(idf, "FilmConstruction") == 1
    assert win.Construction_Name == "FilmConstruction"

    # Standard outputs the parser needs are appended.
    idf_ops.add_standard_outputs(idf)
    assert len(idf.idfobjects["OUTPUT:METER"]) >= 5
    assert len(idf.idfobjects["OUTPUT:VARIABLE"]) >= 3

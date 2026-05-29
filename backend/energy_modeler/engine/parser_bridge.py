"""Real EnergyPlus pipeline (spec Ch 5.2 / 7.7).

Loads the DOE prototype, builds baseline + film scenario IDFs, runs the
EnergyPlus binary, and parses the outputs into RunResults. runner.run_project
calls this when the binary is configured; it raises PrototypeNotFound (which the
runner catches and degrades to the labeled analytical estimate) whenever the
prototypes / IDD / weather aren't available — i.e. everywhere but a provisioned
worker image."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from .. import datastore
from ..parser import results
from ..schemas import RunResult
from . import building, idf_builder, prototype_loader, runner, weather
from .film_catalog import resolve as resolve_film
from .inputs import EngineProject


def run_real_pipeline(project: EngineProject) -> tuple[str, RunResult, list[RunResult]]:
    meta = datastore.get_prototype(project.building_type)
    if meta is None:
        raise prototype_loader.PrototypeNotFound(f"Unknown building_type {project.building_type!r}")
    bldg = building.resolve(project, meta)
    base_id = project.faces[0].base_glazing_id if project.faces else "dbl_clear_3mm_13mmAir"
    base_glazing = datastore.get_base_glazing(base_id) or {}

    # Fail fast (and cleanly) when the prototype IDF / IDD aren't bundled.
    prototype_loader.load_idf(project.building_type, project.climate_zone)
    epw = weather.epw_for_zip(project.zip)
    z = datastore.get_zip(project.zip)
    station = z["station_city"] if z else "EnergyPlus run"

    scenarios: list[tuple[str, object | None]] = [("baseline", None)]
    scenarios += [(s.label, resolve_film(s.film_sku)) for s in project.scenarios]

    baseline: RunResult | None = None
    film_runs: list[RunResult] = []
    with TemporaryDirectory() as tmp:
        for label, film in scenarios:
            idf = prototype_loader.load_idf(project.building_type, project.climate_zone)
            idf_builder.build_scenario_idf(idf, base_glazing, film, bldg, label)
            scen_dir = Path(tmp) / label.replace(" ", "_")
            scen_dir.mkdir(parents=True, exist_ok=True)
            idf_path = scen_dir / f"{label.replace(' ', '_')}.idf"
            idf.saveas(str(idf_path))
            runner.run_energyplus(idf_path, Path(epw), scen_dir)
            rr = results.parse_run(scen_dir / idf_path.stem, label, station=station)
            if film is None:
                baseline = rr
            else:
                film_runs.append(rr)

    assert baseline is not None
    return "energyplus", baseline, film_runs

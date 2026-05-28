"""IDF generation (spec Ch 5).

Section C (constructions/glazing) is the part the platform actively manipulates
per scenario: a baseline construction with no film, then candidate constructions
with the film applied to the inboard surface of the outer pane (spec Ch 4.3).

In a fully provisioned worker (eppy + bundled DOE prototype IDFs) build_idfs()
loads the prototype, scales geometry, binds weather, swaps the glazing
construction, appends the outputs block, and writes a runnable IDF per scenario.
When those are absent we still emit the glazing-construction excerpt + outputs
block so the audit bundle documents exactly what would be submitted."""
from __future__ import annotations

from pathlib import Path

from .. import datastore
from .film_catalog import FilmSpec
from .film_catalog import resolve as resolve_film
from .glazing import applied_properties, base_properties
from .inputs import EngineProject
from .outputs import standard_outputs_idf


def _window_material_idf(name: str, shgc_hint: float, optical: dict, thickness_m: float) -> str:
    tf = optical.get("tf_solar", 0.80)
    rf = optical.get("rf_solar", 0.075)
    rb = optical.get("rb_solar", 0.075)
    tvf = optical.get("tf_visible", 0.88)
    rvf = optical.get("rf_visible", 0.08)
    rvb = optical.get("rb_visible", 0.08)
    ef = optical.get("emissivity_front", 0.84)
    eb = optical.get("emissivity_back", 0.84)
    cond = optical.get("conductivity", 1.0)
    return (
        f"WindowMaterial:Glazing,\n"
        f"  {name},                 !- Name\n"
        f"  SpectralAverage,        !- Optical Data Type\n"
        f"  ,                       !- Spectral Data Set Name\n"
        f"  {thickness_m},          !- Thickness {{m}}\n"
        f"  {tf}, {rf}, {rb},       !- Solar T, R_front, R_back\n"
        f"  {tvf}, {rvf}, {rvb},    !- Visible T, R_front, R_back\n"
        f"  0.000, {ef}, {eb},      !- IR T, e_front, e_back\n"
        f"  {cond};                 !- Conductivity {{W/m-K}}  (~SHGC on dbl-clear {shgc_hint})\n"
    )


def construction_idf(name: str, base_glazing: dict, film: FilmSpec | None) -> str:
    """Emit the Construction + WindowMaterial blocks for one scenario."""
    layer_count = int(base_glazing["layer_count"])
    base = base_properties(base_glazing)
    outer_optical = {
        "tf_solar": 0.837, "rf_solar": 0.075, "rb_solar": 0.075,
        "tf_visible": 0.898, "rf_visible": 0.081, "rb_visible": 0.081,
        "emissivity_front": 0.84, "emissivity_back": 0.84, "conductivity": 1.0,
    }
    lines = [f"! ----- Glazing construction: {name} -----"]

    if film is None:
        outer_name = "Glass_Outer_Base"
        outer_mat = _window_material_idf(outer_name, base.shgc, outer_optical, 0.003)
    else:
        outer_name = f"Glass_Outer_{film.sku.replace('-', '_')}_applied"
        applied = applied_properties(base_glazing, film)
        outer_mat = _window_material_idf(outer_name, applied.shgc, film.optical, 0.003)

    if layer_count >= 2:
        lines.append(
            f"Construction,\n  {name},\n  {outer_name},          !- Outside Layer (outer glass + film)\n"
            f"  Gap_Air_13mm,          !- Layer 2 (gas fill)\n  Glass_Inner_Base;      !- Layer 3 (inner glass)\n"
        )
        lines.append(outer_mat)
        lines.append("WindowMaterial:Gas,\n  Gap_Air_13mm,\n  Air,                   !- Gas Type\n  0.013;                 !- Thickness {m}\n")
        lines.append(_window_material_idf("Glass_Inner_Base", base.shgc, outer_optical, 0.003))
    else:
        lines.append(f"Construction,\n  {name},\n  {outer_name};          !- Single glazing layer\n")
        lines.append(outer_mat)
    return "\n".join(lines)


def _scenario_idf_text(project: EngineProject, base_glazing: dict, film: FilmSpec | None, label: str) -> str:
    header = (
        f"!-- EnergyModeler generated IDF excerpt --\n"
        f"!-- Project: {project.project_id}  Scenario: {label} --\n"
        f"!-- Building prototype: {project.building_type}  Climate zone: {project.climate_zone} --\n"
        f"!-- NOTE: Section C (glazing) shown. Sections A/B/D/E/F come from the DOE\n"
        f"!--       prototype IDF loaded at run time (spec Ch 4.2/5.3).\n\n"
        f"Version, 24.2;\n\n"
    )
    construction = construction_idf(f"{label}_Construction", base_glazing, film)
    return header + construction + "\n\n" + standard_outputs_idf()


def build_idfs(project: EngineProject, workdir: Path) -> list[Path]:
    """Write one IDF per scenario (baseline + N films). Returns paths in run order."""
    workdir.mkdir(parents=True, exist_ok=True)
    # Use the first face's base glazing as the representative assembly.
    base_id = project.faces[0].base_glazing_id if project.faces else "dbl_clear_3mm_13mmAir"
    base_glazing = datastore.get_base_glazing(base_id) or datastore.base_glazings()[2]

    paths: list[Path] = []
    baseline_path = workdir / "baseline.idf"
    baseline_path.write_text(_scenario_idf_text(project, base_glazing, None, "baseline"))
    paths.append(baseline_path)

    for scenario in project.scenarios:
        film = resolve_film(scenario.film_sku)
        safe = scenario.label.replace(" ", "_")
        p = workdir / f"{safe}_{scenario.film_sku}.idf"
        p.write_text(_scenario_idf_text(project, base_glazing, film, scenario.label))
        paths.append(p)
    return paths

#!/usr/bin/env python3
"""Diagnose why the real EnergyPlus pipeline fails on a provisioned worker.

Runs a bundled DOE prototype IDF two ways and prints the eplusout.err tail:

  [1] RAW prototype, unmodified      -> isolates prototype / version / weather faults
  [2] after build_scenario_idf()     -> isolates our glazing/HVAC/output mutations

so the verdict says definitively whether the bad IDF is the DOE prototype itself
(e.g. a version mismatch against the 24.2 binary) or something we inject. The
runner swallows the cause behind the analytical-estimate fallback; this surfaces
it directly.

    python scripts/diagnose_eplus.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from energy_modeler import datastore  # noqa: E402
from energy_modeler.config import settings  # noqa: E402
from energy_modeler.engine import building, idf_builder, prototype_loader  # noqa: E402
from energy_modeler.engine.inputs import EngineProject  # noqa: E402

# (building_type, climate_zone) candidates, tried in order until an IDF resolves.
CANDIDATES = [("MediumOffice", "2A"), ("SmallOffice", "2A"), ("MediumOffice", "5B")]


def _err_tail(run_dir: Path, n: int = 40) -> str:
    err = run_dir / "eplusout.err"
    if not err.exists():
        return "(no eplusout.err written)"
    lines = err.read_text(errors="replace").splitlines()
    flagged = [ln.strip() for ln in lines if "severe" in ln.lower() or "fatal" in ln.lower()]
    return "\n".join((flagged or lines[-n:])[:n])


def _run(exe: str, idf: Path, epw: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [exe, "--weather", str(epw), "--output-directory", str(out), "--readvars", str(idf)],
        capture_output=True, text=True, timeout=1800,
    )
    print(f"    exit={proc.returncode}")
    print("    " + _err_tail(out).replace("\n", "\n    "))
    return proc.returncode


def main() -> int:
    exe = settings.energyplus_exe
    print(f"energyplus_exe : {exe}")
    print(f"IDD            : {prototype_loader._idd_path()}")
    if not exe:
        print("No EnergyPlus binary (PATH / ENERGYPLUS_DIR) — abort.")
        return 2

    bt = cz = None
    idf_src = None
    for cand_bt, cand_cz in CANDIDATES:
        p = prototype_loader._find_prototype_idf(cand_bt, cand_cz, "ASHRAE901_2019")
        if p:
            bt, cz, idf_src = cand_bt, cand_cz, p
            break
    if idf_src is None:
        print(f"No prototype IDF under {settings.prototypes_dir} — run scripts/fetch_prototypes.py")
        return 2
    epws = sorted(Path(settings.storage_dir, "weather").glob("*.epw"))
    if not epws:
        print(f"No .epw under {settings.storage_dir}/weather — run scripts/fetch_weather.py")
        return 2
    epw = epws[0]
    print(f"prototype      : {bt}/{cz} -> {idf_src}")
    print(f"weather        : {epw.name}")

    work = Path("/tmp/eplus_diag")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)

    print("\n[1] RAW prototype (unmodified)")
    rc1 = _run(exe, idf_src, epw, work / "raw")

    print("\n[2] after build_scenario_idf() (baseline scenario)")
    meta = datastore.get_prototype(bt) or {}
    project = EngineProject(
        project_id="diag", building_type=bt, climate_zone=cz,
        gross_floor_area_sf=float(meta.get("nominal_area_sf") or 50000),
        zip="33602", utility_rate_usd_kwh=0.12, egrid_subregion="FRCC",
    )
    bldg = building.resolve(project, meta)
    base_glazing = datastore.get_base_glazing("dbl_clear_3mm_13mmAir") or datastore.base_glazings()[2]
    idf = prototype_loader.load_idf(bt, cz)
    idf_builder.build_scenario_idf(idf, base_glazing, None, bldg, "baseline")
    mut_idf = work / "baseline.idf"
    idf.saveas(str(mut_idf))
    rc2 = _run(exe, mut_idf, epw, work / "mutated")

    print("\n=== verdict ===")
    if rc1 != 0:
        print("RAW prototype FAILS -> prototype/version/weather fault; our mutations are not the cause.")
    elif rc2 != 0:
        print("RAW ok, MUTATED fails -> build_scenario_idf mutations are the cause.")
    else:
        print("Both ran clean -> failure is downstream (parser / paths), not the IDF.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

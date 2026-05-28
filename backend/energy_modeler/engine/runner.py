"""Run orchestration (spec Ch 5/9.4).

Selects the calculation engine: the real EnergyPlus subprocess when the binary
is configured and prototype IDFs are present, otherwise the labeled analytical
estimate. Returns (engine_mode, baseline RunResult, [film RunResults])."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import settings
from ..schemas import RunResult
from . import estimate
from .inputs import EngineProject


def _energyplus_available() -> bool:
    return settings.energyplus_exe is not None


def run_energyplus(idf_path: Path, weather_path: Path, output_dir: Path) -> str:
    """Invoke the EnergyPlus binary on one IDF. Returns the run id (output dir name).

    Raises CalledProcessError on a non-zero exit so the worker can mark the job
    failed and surface the stderr tail (spec Ch 10.3 error envelope)."""
    exe = settings.energyplus_exe
    if exe is None:
        raise RuntimeError("EnergyPlus binary not available")
    run_dir = output_dir / idf_path.stem
    run_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [exe, "--weather", str(weather_path), "--output-directory", str(run_dir),
         "--readvars", str(idf_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    return idf_path.stem


def run_project(project: EngineProject) -> tuple[str, RunResult, list[RunResult]]:
    """Run baseline + candidate scenarios. Falls back to the estimate engine when
    EnergyPlus is unavailable (the expected beta path)."""
    if not _energyplus_available():
        baseline, films = estimate.run_project(project)
        return "analytical_estimate", baseline, films

    # Real EnergyPlus path. Requires bundled DOE prototype IDFs + eppy in the
    # worker image; integrated end-to-end in Phase 1 weeks 6-8 (spec Ch 11.5).
    try:
        from .parser_bridge import run_real_pipeline  # type: ignore

        return run_real_pipeline(project)
    except Exception:  # noqa: BLE001 - degrade to a labeled estimate, never crash a beta run
        baseline, films = estimate.run_project(project)
        for run in [baseline, *films]:
            run.warnings.append(
                "EnergyPlus binary detected but the full IDF pipeline is not yet "
                "provisioned (missing prototype IDFs/eppy); used analytical estimate."
            )
        return "analytical_estimate", baseline, films

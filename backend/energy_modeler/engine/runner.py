"""Run orchestration (spec Ch 5/9.4).

Selects the calculation engine: the real EnergyPlus subprocess when the binary
is configured and prototype IDFs are present, otherwise the labeled analytical
estimate. Returns (engine_mode, baseline RunResult, [film RunResults])."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import settings
from ..schemas import RunResult
from . import estimate, prototype_loader
from .inputs import EngineProject


class EnergyPlusError(RuntimeError):
    """EnergyPlus exited non-zero. The message carries the severe/fatal lines
    from eplusout.err so the failure is diagnosable from the job record instead
    of being swallowed by the analytical-estimate fallback (spec Ch 10.3)."""


def _eplus_err_tail(run_dir: Path, max_lines: int = 40) -> str:
    """Pull the severe/fatal lines out of eplusout.err. EnergyPlus writes the
    actual rejection reason here, not to stderr (which only says 'Error(s)
    Detected')."""
    err = run_dir / "eplusout.err"
    if not err.exists():
        return "(no eplusout.err written)"
    lines = err.read_text(errors="replace").splitlines()
    flagged = [ln.strip() for ln in lines if "severe" in ln.lower() or "fatal" in ln.lower()]
    return "\n".join((flagged or lines[-max_lines:])[:max_lines])


def _energyplus_available() -> bool:
    return settings.energyplus_exe is not None


def run_energyplus(idf_path: Path, weather_path: Path, output_dir: Path) -> str:
    """Invoke the EnergyPlus binary on one IDF. Returns the run id (output dir name).

    Raises EnergyPlusError (with the eplusout.err severe/fatal tail) on a non-zero
    exit so the worker can mark the job failed and surface the cause (spec Ch 10.3
    error envelope)."""
    exe = settings.energyplus_exe
    if exe is None:
        raise RuntimeError("EnergyPlus binary not available")
    run_dir = output_dir / idf_path.stem
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [exe, "--weather", str(weather_path), "--output-directory", str(run_dir),
             "--readvars", str(idf_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.CalledProcessError as exc:
        # Read eplusout.err now — before any caller's TemporaryDirectory is torn
        # down — and attach the real cause to the raised error.
        raise EnergyPlusError(
            f"EnergyPlus exited {exc.returncode} on {idf_path.name}.\n{_eplus_err_tail(run_dir)}"
        ) from exc
    return idf_path.stem


def run_project(
    project: EngineProject,
) -> tuple[str, RunResult, list[RunResult], RunResult | None]:
    """Run baseline + candidate scenarios. Falls back to the estimate engine when
    EnergyPlus is unavailable (the expected beta path).

    Returns (engine_mode, baseline, film_runs, appendix_g_run). The 4th element
    is the ASHRAE 90.1-2019 Appendix G baseline run when
    CalcOptions.include_appendix_g_baseline=true AND the real EnergyPlus path is
    taken; else None. The analytical-estimate fallback never produces an
    Appendix G run (the spec calls for the unmodified DOE prototype + ASHRAE
    140-validated engine, which the estimate is not)."""
    if not _energyplus_available():
        baseline, films = estimate.run_project(project)
        return "analytical_estimate", baseline, films, None

    # Real EnergyPlus path. Requires bundled DOE prototype IDFs + eppy in the
    # worker image; integrated end-to-end in Phase 1 weeks 6-8 (spec Ch 11.5).
    try:
        from .parser_bridge import run_real_pipeline  # type: ignore

        return run_real_pipeline(project)
    except prototype_loader.PrototypeNotFound as exc:
        detail = (
            "EnergyPlus binary detected but the prototype IDFs / IDD / weather are "
            f"not provisioned ({exc}); used analytical estimate."
        )
    except Exception as exc:  # noqa: BLE001 - degrade to a labeled estimate, never crash a beta run
        # The result is the analytical estimate, NOT a bid-grade simulation; carry
        # the actual EnergyPlus failure (e.g. the eplusout.err tail) into the
        # warning so it is visible on the job rather than silently hidden.
        detail = f"EnergyPlus run failed; result is an analytical estimate, NOT bid-grade. Cause: {exc}"
    baseline, films = estimate.run_project(project)
    for run in [baseline, *films]:
        run.warnings.append(detail)
    return "analytical_estimate", baseline, films, None

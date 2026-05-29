"""runner error-surfacing (spec Ch 10.3): an EnergyPlus failure must carry the
eplusout.err cause into the job warning instead of being hidden behind the
generic 'not provisioned' fallback message."""
from pathlib import Path

from energy_modeler.engine import runner
from energy_modeler.engine.inputs import EngineFace, EngineProject, EngineScenario


def _project():
    return EngineProject(
        project_id="err", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540", utility_rate_usd_kwh=0.11,
        egrid_subregion="X",
        faces=[EngineFace("S", 873, "dbl_clear_3mm_13mmAir")],
        scenarios=[EngineScenario("PR40X", "3M-PR40X", 43675)],
    )


def test_err_tail_extracts_severe_and_fatal(tmp_path: Path):
    (tmp_path / "eplusout.err").write_text(
        "Program Version EnergyPlus 24.2\n"
        "   ** Warning ** something benign\n"
        "   ** Severe  ** Window construction missing layer\n"
        "   **  Fatal  ** Errors found, program terminates\n"
        "   ...Summary: Last severe error=Window construction missing layer\n"
    )
    tail = runner._eplus_err_tail(tmp_path)
    assert "Severe" in tail and "Fatal" in tail
    assert "Window construction missing layer" in tail
    assert "benign" not in tail  # warnings are dropped; only severe/fatal kept


def test_err_tail_missing_file(tmp_path: Path):
    assert "no eplusout.err" in runner._eplus_err_tail(tmp_path)


def test_run_project_surfaces_eplus_cause(monkeypatch):
    # Pretend the binary is present, but make the real pipeline raise a
    # representative EnergyPlus failure; the cause must reach the run warning.
    monkeypatch.setattr(runner, "_energyplus_available", lambda: True)

    import energy_modeler.engine.parser_bridge as pb

    def _boom(project):
        raise runner.EnergyPlusError("EnergyPlus exited 1 on baseline.idf.\n** Severe ** bad glazing")

    monkeypatch.setattr(pb, "run_real_pipeline", _boom)

    mode, baseline, films = runner.run_project(_project())
    assert mode == "analytical_estimate"
    assert any("EnergyPlus run failed" in w and "bad glazing" in w for w in baseline.warnings)

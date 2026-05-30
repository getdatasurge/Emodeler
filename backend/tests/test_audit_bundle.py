"""Per-project audit bundle: every artifact in the bundle is hashed in
MANIFEST.sha256 so a reviewer can verify any file independently, and
CITATIONS.md names every upstream standard with the exact source used."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.pipeline import _citations_text, _sha256, _write_manifest, build_audit_bundle
from energy_modeler.config import settings
from energy_modeler.engine.inputs import (
    EngineFace,
    EngineOptions,
    EngineProject,
    EngineScenario,
)
from energy_modeler.schemas import (
    EnergyEndUses,
    FilmComparison,
    PeakDemand,
    ProjectComparison,
    RunResult,
)


def _engine_project(gas_rate=None) -> EngineProject:
    return EngineProject(
        project_id="proj-x", building_type="MediumOffice", climate_zone="2A",
        gross_floor_area_sf=14500, zip="33540",
        utility_rate_usd_kwh=0.1145, gas_rate_usd_therm=gas_rate,
        egrid_subregion="FRCC",
        faces=[EngineFace("S", 873, "dbl_clear_3mm_13mmAir")],
        scenarios=[EngineScenario("Good", "3M-PR40X", 25000)],
        options=EngineOptions(),
    )


def _run(label: str) -> RunResult:
    return RunResult(
        run_id=label, scenario_label=label, engine_mode="energyplus",
        energyplus_version="22.1.0", weather_station="TAMPA INTL AP",
        weather_dataset="TMY3",
        annual_end_uses=EnergyEndUses(
            cooling_elec_kwh=80000.0, heating_elec_kwh=2000.0,
            interior_lighting_kwh=45000.0, fans_kwh=25000.0,
            total_electricity_kwh=170000.0,
        ),
        peak_demand=PeakDemand(cooling_peak_kw=44.4, total_facility_peak_kw=100.0),
        windows=[], monthly_cooling_kwh=[6667.0] * 12, warnings=[],
    )


def _comparison() -> ProjectComparison:
    baseline = _run("baseline")
    film = _run("Good")
    return ProjectComparison(
        project_id="proj-x", engine_mode="energyplus",
        generated_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
        baseline=baseline, film_runs=[film],
        films=[FilmComparison(
            scenario_label="Good", film_sku="3M-PR40X",
            delta_cooling_kwh=10000.0, delta_heating_kwh=-500.0,
            delta_total_kwh=10000.0, delta_gas_kwh=0.0,
            delta_peak_kw=5.0, delta_cost_usd_per_year=1145.0,
            delta_co2_lb_per_year=8000.0, project_cost_usd=25000.0,
            simple_payback_years=21.8, npv_15yr_usd=-5000.0, irr_15yr_pct=2.0,
            monthly_cooling_savings_kwh=[833.3] * 12,
        )],
    )


def test_sha256_matches_python_hash(tmp_path: Path):
    p = tmp_path / "data.bin"
    p.write_bytes(b"hello, audit bundle\n")
    expected = hashlib.sha256(b"hello, audit bundle\n").hexdigest()
    assert _sha256(p) == expected


def test_write_manifest_lists_every_file_with_its_hash(tmp_path: Path):
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("beta")
    manifest = _write_manifest(tmp_path)
    lines = manifest.read_text().strip().splitlines()
    paths = [ln.split("  ", 1)[1] for ln in lines]
    # Sorted, posix-style relative paths, MANIFEST itself excluded.
    assert paths == ["a.txt", "sub/b.txt"]
    # Each hash is a 64-char hex string.
    assert all(len(ln.split("  ", 1)[0]) == 64 for ln in lines)


def test_citations_names_all_upstream_standards():
    text = _citations_text(_engine_project(), _comparison())
    for marker in [
        "EnergyPlus 22.1.0", "ASHRAE 140",
        "DOE Commercial Prototype", "ASHRAE 90.1-2019",
        "TMY3", "TAMPA INTL AP",
        "LBNL IGSDB", "NFRC 200", "3M angular optics",
        "EPA eGRID 2023", "FRCC",
        "ISO 15099",
    ]:
        assert marker in text, f"citation missing: {marker!r}"


def test_citations_records_no_gas_rate_when_unset():
    text = _citations_text(_engine_project(gas_rate=None), _comparison())
    assert "NOT SET" in text


def test_audit_bundle_writes_manifest_and_citations(tmp_path: Path, monkeypatch):
    # Redirect storage_dir to a clean tmp so the bundle lands there.
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    archive = build_audit_bundle("proj-x", _engine_project(), _comparison())
    assert Path(archive).exists()
    bundle_dir = tmp_path / "proj-x" / "audit"
    assert (bundle_dir / "MANIFEST.sha256").exists()
    assert (bundle_dir / "CITATIONS.md").exists()
    assert (bundle_dir / "METHODOLOGY.txt").exists()
    assert (bundle_dir / "results.json").exists()
    # The manifest covers results.json (round-trip the hash).
    manifest = (bundle_dir / "MANIFEST.sha256").read_text()
    expected_results_hash = _sha256(bundle_dir / "results.json")
    assert f"{expected_results_hash}  results.json" in manifest
    # results.json round-trips as JSON.
    json.loads((bundle_dir / "results.json").read_text())

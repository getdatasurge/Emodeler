"""Hybrid scaling: baseline absolutes scale by floor ratio, film deltas scale
by glazing ratio. This is the physically correct treatment because internal
loads + non-window cooling track building size, while window-film savings
track glass area.

Replaces the prior uniform-floor default that under-claimed savings on
glazing-heavy projects (e.g. FX-01: 24% glazing-to-floor vs the prototype's
13% — uniform floor scaling clipped the film effect by ~half)."""
from energy_modeler.engine.parser_bridge import _scale_runs_hybrid
from energy_modeler.schemas import EnergyEndUses, PeakDemand, RunResult


def _run(
    *,
    cooling: float = 0.0,
    heating_elec: float = 0.0,
    lighting: float = 0.0,
    equipment: float = 0.0,
    fans: float = 0.0,
    peak_cool: float = 0.0,
    peak_total: float = 0.0,
) -> RunResult:
    elec_total = cooling + heating_elec + lighting + equipment + fans
    return RunResult(
        run_id="r", scenario_label="x", engine_mode="energyplus",
        energyplus_version="22.1.0", weather_station="TPA",
        weather_dataset="TMY3",
        annual_end_uses=EnergyEndUses(
            cooling_elec_kwh=cooling,
            heating_elec_kwh=heating_elec,
            interior_lighting_kwh=lighting,
            interior_equipment_kwh=equipment,
            fans_kwh=fans,
            total_electricity_kwh=elec_total,
        ),
        peak_demand=PeakDemand(
            cooling_peak_kw=peak_cool,
            total_facility_peak_kw=peak_total,
        ),
        windows=[],
        monthly_cooling_kwh=[cooling / 12] * 12 if cooling else [],
        warnings=[],
    )


def test_baseline_absolutes_scale_by_floor_factor():
    """Baseline's whole-building absolutes are the project's actual building
    energy — they track floor area, not glazing."""
    baseline = _run(cooling=100_000, equipment=200_000)
    factors = {"floor": 0.5, "glazing": 0.3,
               "project_floor_sf": 25_000, "proto_floor_sf": 50_000,
               "project_glazing_sf": 1_500, "proto_glazing_sf": 5_000}
    _scale_runs_hybrid(baseline, [], None, factors)
    assert baseline.annual_end_uses.cooling_elec_kwh == 50_000.0
    assert baseline.annual_end_uses.interior_equipment_kwh == 100_000.0


def test_film_delta_scales_by_glazing_factor_not_floor():
    """The film effect is a *delta* on top of the baseline. With hybrid
    scaling that delta tracks glazing area (the film only acts on glass)."""
    baseline = _run(cooling=100_000, equipment=200_000)
    film = _run(cooling=80_000, equipment=200_000)  # 20,000 kWh proto savings
    factors = {"floor": 0.5, "glazing": 0.3,
               "project_floor_sf": 0, "proto_floor_sf": 0,
               "project_glazing_sf": 0, "proto_glazing_sf": 0}
    _scale_runs_hybrid(baseline, [film], None, factors)

    # baseline cooling: 100,000 * 0.5 = 50,000
    assert baseline.annual_end_uses.cooling_elec_kwh == 50_000.0
    # film cooling: baseline_scaled - proto_delta * glazing_factor
    #             = 50,000 - 20,000 * 0.3 = 44,000
    assert film.annual_end_uses.cooling_elec_kwh == 44_000.0


def test_equipment_in_film_run_equals_baseline_run():
    """Plug-load equipment doesn't respond to a window film. The hybrid scaler
    overwrites the film's equipment field with the baseline's so the delta
    is exactly zero — no spurious 'savings' from a uniform scale of an
    unrelated end-use."""
    baseline = _run(cooling=100_000, equipment=200_000)
    film = _run(cooling=80_000, equipment=200_000)
    factors = {"floor": 0.5, "glazing": 0.3,
               "project_floor_sf": 0, "proto_floor_sf": 0,
               "project_glazing_sf": 0, "proto_glazing_sf": 0}
    _scale_runs_hybrid(baseline, [film], None, factors)
    assert (
        film.annual_end_uses.interior_equipment_kwh
        == baseline.annual_end_uses.interior_equipment_kwh
    )


def test_fx01_numbers_land_above_floor_only_result():
    """Concrete check against the FX-01 console paste:
       proto baseline cooling 198,139 kWh, proto Good cooling 154,183 kWh,
       floor ratio 0.2704, glazing ratio 0.5076.
    With the prior uniform-floor scaling, the Good film delta was 43,956 *
    0.2704 = 11,886 kWh. With hybrid, the film delta is 43,956 * 0.5076 =
    22,317 kWh — roughly 1.88x larger, matching the per-glazing-sqft argument."""
    baseline = _run(
        cooling=198_139, heating_elec=1_819, lighting=63_869,
        equipment=195_953, fans=35_267,
        peak_cool=44.4, peak_total=100.0,
    )
    film = _run(
        cooling=154_183, heating_elec=3_072, lighting=64_181,
        equipment=195_953, fans=23_947,
        peak_cool=39.4, peak_total=98.0,
    )
    factors = {"floor": 0.2704, "glazing": 0.5076,
               "project_floor_sf": 14_500, "proto_floor_sf": 53_628,
               "project_glazing_sf": 3_494, "proto_glazing_sf": 6_883}
    _scale_runs_hybrid(baseline, [film], None, factors)

    # baseline cooling at project scale (floor)
    assert abs(baseline.annual_end_uses.cooling_elec_kwh - 198_139 * 0.2704) < 1.0
    # film delta in cooling = proto_delta * glazing
    expected_delta = (198_139 - 154_183) * 0.5076  # ≈ 22,323
    actual_delta = (
        baseline.annual_end_uses.cooling_elec_kwh
        - film.annual_end_uses.cooling_elec_kwh
    )
    assert abs(actual_delta - expected_delta) < 1.5
    # equipment unchanged between baseline + film (no plug-load delta)
    assert (
        baseline.annual_end_uses.interior_equipment_kwh
        == film.annual_end_uses.interior_equipment_kwh
    )


def test_hybrid_total_electricity_is_recomputed_from_components():
    """After hybrid adjusts component fields, total_electricity_kwh must be
    re-summed from the components — otherwise the delta-total reported in
    the UI mixes scaled and unscaled numbers."""
    baseline = _run(cooling=100, heating_elec=20, lighting=30,
                    equipment=40, fans=10)
    film = _run(cooling=80, heating_elec=22, lighting=31,
                equipment=40, fans=8)
    factors = {"floor": 1.0, "glazing": 1.0,
               "project_floor_sf": 0, "proto_floor_sf": 0,
               "project_glazing_sf": 0, "proto_glazing_sf": 0}
    _scale_runs_hybrid(baseline, [film], None, factors)
    eu = film.annual_end_uses
    expected_total = (
        eu.heating_elec_kwh + eu.cooling_elec_kwh
        + eu.interior_lighting_kwh + eu.interior_equipment_kwh
        + eu.fans_kwh + eu.pumps_kwh + eu.heat_rejection_kwh
    )
    assert abs(eu.total_electricity_kwh - expected_total) < 0.5


def test_hybrid_short_circuits_when_both_factors_are_one():
    """All-1.0 factors mean nothing to scale — the runs must come out
    byte-identical so a same-size-as-prototype project isn't perturbed."""
    baseline = _run(cooling=100_000, equipment=50_000)
    film = _run(cooling=80_000, equipment=50_000)
    before_b = baseline.annual_end_uses.cooling_elec_kwh
    before_f = film.annual_end_uses.cooling_elec_kwh
    factors = {"floor": 1.0, "glazing": 1.0,
               "project_floor_sf": 0, "proto_floor_sf": 0,
               "project_glazing_sf": 0, "proto_glazing_sf": 0}
    _scale_runs_hybrid(baseline, [film], None, factors)
    assert baseline.annual_end_uses.cooling_elec_kwh == before_b
    assert film.annual_end_uses.cooling_elec_kwh == before_f

# M&V methodology — ESCO / performance-contract use

How EnergyModeler outputs support measurement & verification for guaranteed-
savings contracts, and what a PE reviews before the numbers back a guarantee.

## IPMVP option mapping
EnergyModeler is a **whole-building simulation** tool, so it maps to **IPMVP
Option D — Calibrated Simulation**:
- **Baseline** = the EnergyPlus run of the DOE prototype with the existing
  glazing (and, where supplied, as-built HVAC COP + envelope).
- **Proposed** = the same model with the 3M film applied (outer-pane glazing
  construction swap; EnergyPlus solves angular optics per timestep).
- **Savings** = baseline − proposed annual energy/cost/demand.

**For a contractually guaranteed number**, the baseline model must be
**calibrated to ≥12 months of utility bills** (IPMVP Option D calibration —
roadmap item). Absent calibration, results are **TMY3 expected savings**, valid
for design/bid, not a settled guarantee. The analytical estimate is **never**
M&V-grade (it's stamped "not for bids").

## What the audit bundle provides (reproducibility — spec Ch 2.5)
Every run packages a bundle a third party (or PE, or the owner's engineer) can
independently re-run:
- proposed + baseline IDFs (and the Appendix G baseline IDF for LEED),
- the TMY3 `.epw` reference,
- IGSDB record IDs for every glazing/film layer,
- `eplusout.eso` / `eplusout.err` / `eplustbl.csv`,
- the parsed `ProjectComparison.json`,
- the methodology statement (engine version + data-source versions).

Re-running the proposed IDF reproduces the reported end-uses to machine epsilon.

## PE-stamp review checklist (spec §8.4)
Before the methodology backs a guarantee, a licensed mechanical engineer confirms:
- [ ] Engine = unmodified EnergyPlus 24.2 (inherits DOE's ASHRAE 140 validation).
- [ ] Prototype source + standard edition (PNNL 90.1-2019) appropriate to the building.
- [ ] As-built overrides (HVAC COP, envelope) sourced (nameplate / audit), not guessed.
- [ ] Glazing optics from IGSDB (NFRC 200), spectral or summary tier documented.
- [ ] No HVAC resizing between baseline and film (retrofit rule).
- [ ] `eplusout.err` severe warnings reviewed.
- [ ] Cross-check vs. EFILM documented (`EFILM_CROSSCHECK.md`), divergences attributed.
- [ ] Five reference fixtures (FX-01…05) pass the published ranges.

## Limitations to disclose
- TMY3 ≠ actual weather year; expected savings vary with weather.
- Single-SHGC / analytical methods (eQuest, TRACE, the bundled estimate) are not
  acceptable for guarantees (spec §2.1) — only the calibrated EnergyPlus path.
- Demand-charge / TOU bill impact is modeled separately (Phase 3 economics).

> Status: framing + audit reproducibility are in place; Option D **calibration to
> utility bills** and the PE sign-off are executed once the EnergyPlus engine is
> running and validated on the host.

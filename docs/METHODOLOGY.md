# Methodology & Validation

## Why EnergyPlus (not a single-SHGC formula)

A window's SHGC is a function of solar incidence angle, not a single number. 3M's
own guidance is explicit: *"you should NEVER model the performance of the film by
entering in a single SHGC value … EnergyPlus will not allow users to enter a
single value."* EnergyPlus solves the full layer-by-layer angular heat balance
(ISO 15099 convection), which is auditable by utilities, rebate programs, and
PE reviewers. EnergyModeler does **not** roll its own thermal model.

## Glazing methodology hierarchy (spec Ch 2.4)

| Priority | Method |
|---|---|
| 1 — Best | `WindowMaterial:Glazing` with full IGSDB spectral data; EnergyPlus computes angular optics |
| 2 — Good | `WindowMaterial:Glazing` with IGSDB summary values + EnergyPlus default angular curves |
| 3 — Fallback | `WindowMaterial:SimpleGlazingSystem` (rated U + SHGC) — rare for 3M products |
| Never | A user-facing single-SHGC analytical calculation — forbidden by 3M, rejected by EnergyPlus |

## Engine modes in this codebase

- **`energyplus`** (production): `engine/idf_builder.py` swaps the outer-pane
  glazing record for the IGSDB-measured glass+film system (spec Ch 5.4), writes
  one IDF per scenario, and `engine/runner.py` runs the binary and parses output.
  Active when `ENERGYPLUS_DIR` + DOE prototype IDFs are present.
- **`analytical_estimate`** (beta fallback, `engine/estimate.py`): a transparent
  physics-lite estimator used only when EnergyPlus is unavailable. Per-face,
  per-month transmitted-solar reduction `POA × area × (SHGC_base − SHGC_film)`,
  split by a per-climate-zone seasonal mask into cooling savings (÷ COP) and a
  heating penalty. **Clearly labeled and not valid for bids** — this is the
  exact "single-SHGC shortcut" the methodology forbids for deliverables, kept
  only so the platform is demonstrable end to end. It carries a warning on every
  result and in the audit bundle.

## Audit defensibility (spec Ch 2.5)

Every completed analysis produces a downloadable audit bundle containing the
scenario IDFs, the parsed `results.json`, and a `METHODOLOGY.txt` statement
(EnergyPlus version, data sources, standards). A third party can re-run the
inputs and reproduce the numbers.

## Validation fixtures (spec Ch 12.1)

Five reference projects span climate zones and building types. **Strict output
ranges below are the acceptance criteria for the EnergyPlus path.** When running
the analytical fallback, `tests/test_engine.py` instead asserts physical
self-consistency (savings positive and bounded by baseline cooling, cold-climate
heating penalty present, finite economics) — a 20–30% spread vs. the dealer's
Excel sanity point is expected and acceptable.

| Fixture | Profile | Film | Expected (EnergyPlus path) |
|---|---|---|---|
| FX-01 Zephyrhills FL | Medium Office, 14,500 sf, dual-pane clear, ZIP 33540 (CZ 2A) | PR40X | Cooling Δ 55–80k kWh/yr · $4.2–7.2k/yr · payback 6.0–10.5 yr |
| FX-02 Anoka-Hennepin MN | Secondary School, 210k sf, dual-pane low-E, ZIP 55303 (CZ 6A) | NV35 | Cooling Δ 80–115k · heating penalty 8–15k · net $2.8–5.2k/yr |
| FX-03 Academy 20 CO | Primary School, 75k sf, dual-pane clear, ZIP 80921 (CZ 5B) | TH40 | Cooling Δ 40–60k · heating Δ −5k…+2k (Thinsulate low-e) |
| FX-04 Richland County SC | Secondary School, 180k sf, single-pane bronze, ZIP 29203 (CZ 3A) | PR50X | Cooling Δ 150–215k · $12–19k/yr · payback 4.5–7.5 yr |
| FX-05 Vineland NJ | Secondary School, 220k sf, dual-pane clear, ZIP 08360 (CZ 4A) | S140 | Cooling Δ 70–100k · heating Δ −4k…−10k · payback 9–14 yr |

### Three-tier validation strategy
1. **IGSDB reproduction** — film SHGC/U/VT on dual-pane-clear within 5% / 5% / 2% of the IGSDB summary.
2. **Reference project ranges** — full pipeline output within the ranges above.
3. **Independent PE review** (pre-Phase-3) — licensed engineer signs off on the methodology for stamped reports.

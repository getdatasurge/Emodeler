# EFILM cross-check protocol (spec §8.6 / §12.2)

How we compare EnergyModeler against the tool it replaces, **3M/IWFA EFILM**, and
how we account for the differences. **This is not a pass/fail gate** — EFILM is a
useful baseline, not ground truth. The citable references are the EnergyPlus
version and the IGSDB record IDs in the audit bundle, not EFILM.

## What EFILM is
A Windows desktop GUI on **EnergyPlus 8.0** (Sept 2014, frozen). Same engine
*family* as ours (**EnergyPlus 22.1**), about eight years older. Same workflow shape:
ZIP → TMY3, DOE prototype scaled to floor area, base glass + one 3M film, swap
the outer-pane `WindowMaterial:Glazing` for the IGSDB film-on-glass record, run,
parse, branded PDF. One film per run (we do baseline + N in one pass).

## Procedure (run on FX-01 Zephyrhills FL)
1. In the dealer's EFILM install, run FX-01 exactly per spec §12.1 (Medium
   Office, 14,500 sf, dual-pane clear, 3,494 sf glazing, ZIP 33540, PR40X).
   Capture: annual electricity (kWh), annual cooling savings (kWh), annual $
   savings, payback (yr), and the PDF.
2. Run the same project in EnergyModeler (EnergyPlus engine, not the analytical
   estimate). Capture the same metrics from the results dashboard + audit bundle.
3. Compute the per-metric % delta.

## Acceptance bands
| Metric | Target | Investigate | Block |
|---|---|---|---|
| Annual cooling savings | ±10% | 10–20% | >20% |
| Annual electricity (baseline) | ±15% | — | — |
| Annual $ savings | ±10% | — | — |
| Simple payback | ±15% | — | — |

A delta outside the band must be **attributed** to one of the legitimate
divergences below; an unattributable delta is treated as a bug.

## Legitimate sources of divergence (expected, documented)
- **EnergyPlus version (8.0 → 22.1).** ISO 15099 §8.3.2.2 interior convection
  (8.0 used a flat 1.46 W/m²·K ASHRAE constant), improved shading/blind models,
  IGU deflection, refined `Daylighting:Controls`, updated coil performance
  curves. Expect 5–10% on annual cooling for identical inputs.
- **Prototype recalibration.** PNNL re-issued the DOE Commercial Prototypes for
  90.1-2016 and 90.1-2019 (we ship 2019; EFILM ships ~2010). Schedules, LPD, and
  equipment power densities moved → different baseline EUI.
- **IGSDB freshness.** EFILM caches optical data at install; we pull weekly. When
  3M re-rates a film, our SHGC moves and EFILM's doesn't.
- **Frame model.** EFILM is center-of-glass U only; we add
  `WindowProperty:FrameAndDivider` (NFRC whole-window U), ~5–10% higher U.

## Why we don't match eQuest / TRACE 700 / the Excel calculator
All three allow a **single-SHGC** glazing input — the method 3M says *never* use
(spec §2.1), because it ignores the angular dependence EnergyPlus models per
timestep. Expected spread vs. those tools is 20–30% and is **not** a defect in
our results. If a reviewer brings them, the response is the §2.1 citation +
"EnergyPlus solves T(θ)/R(θ)/A(θ) natively; single-SHGC tools don't."

## ASHRAE 140 inheritance
We don't run Standard 140 ourselves — EnergyPlus is validated against it by DOE,
and by running the **unmodified** binary we inherit that validation. Stated on
the methodology page of every report.

> Status: protocol defined. Execution requires the EnergyPlus engine (Weeks 7–8)
> running against the real 22.1 binary + bundled DOE prototypes, plus access to a
> dealer EFILM install. Results land in this file once run.

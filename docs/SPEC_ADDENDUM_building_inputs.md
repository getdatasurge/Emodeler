# Spec addendum — As-built building characterization

> Expands the EnergyModeler Technical Specification (Ch 5.3 *Prototype loading &
> scaling*, Ch 6 *Results*, Ch 9.3 *Database schema*, Ch 11.2.1 *Project setup
> form*). Status: implemented for the analytical estimate; envelope/operations
> become fully active in the EnergyPlus engine.

## 1. Motivation

The base spec models a building by selecting a DOE prototype (`building_type` +
`climate_zone`), scaling it to `gross_floor_area_sf`, and overriding only the
glazing. HVAC efficiency, wall/roof construction, and operating schedule are
inherited from the prototype's per-area defaults. For window-film analysis that
hides the two biggest sensitivities after glazing:

- **HVAC cooling COP** sets the electricity saved per unit of solar load
  rejected (`cooling_kWh ≈ solar_load / COP`). An old RTU (COP ~2.5) and a new
  chiller (COP ~5.0) produce ~2× different savings for the *same* film.
- **Opaque envelope (wall/roof area, U-factor, solar absorptance)** sets how
  much of the building's load is conductive vs. solar — i.e. how large a lever
  the windows are — and the winter heating penalty.

This addendum adds an **optional as-built characterization layer**. Every field
is nullable and falls back to a prototype or ASHRAE 90.1-2019 climate-zone
default, so the fast path is unchanged and pros can refine.

## 2. Input set

| Group | Field | Units | Default source |
|---|---|---|---|
| HVAC | `hvac_cooling_cop` | COP (W/W) | prototype `cop` |
| HVAC | `hvac_heating_cop` | COP (W/W) | 3.0 |
| HVAC | `hvac_system_type` | enum | `packaged_dx` |
| Walls | `wall_area_sf` | ft² | derived from geometry − glazing |
| Walls | `wall_u_factor` | BTU/h·ft²·F | ASHRAE 90.1 by climate zone |
| Walls | `wall_absorptance` | 0–1 | 0.60 |
| Roof | `roof_area_sf` | ft² | building footprint |
| Roof | `roof_type` | enum | `membrane` |
| Roof | `roof_u_factor` | BTU/h·ft²·F | ASHRAE 90.1 by climate zone |
| Roof | `roof_absorptance` | 0–1 | 0.70 (cool roof ≈ 0.30) |
| Operations | `operating_hours_per_week` | h | prototype `operating_hours` |
| Geometry | `num_floors` | int | prototype `floors` |
| Geometry | `floor_to_floor_ft` | ft | 13 |

Cooling/heating COP accept EER/SEER on the roadmap (converted to COP on input).

## 3. Data model & API

- **`projects`** gains the 13 nullable columns above (single canonical list in
  `energy_modeler/engine/inputs.py::BUILDING_FIELDS`, shared by the ORM model,
  the API schema, and the persistence→engine mapping so they cannot drift).
- **API**: `ProjectCreate` / `ProjectUpdate` extend a validated `BuildingInputs`
  model (range checks: COP 0–10, absorptance 0–1, hours ≤168, etc.).
- **Intake UI** (Ch 11.2.1): a collapsible *Building details (advanced)* section,
  pre-filled with placeholders that name the default for each field.

## 4. Engine treatment

`engine/building.py::resolve(project, prototype)` produces a `ResolvedBuilding`
that fills every blank from prototype/climate defaults and records a per-field
`user` | `default` **provenance map**.

**Analytical estimate** (`engine/estimate.py`):
- Cooling and heating **COP** are now resolved per project (was a hard-coded
  3.0) — the dominant, well-bounded fidelity lever.
- **Window conduction** is modeled as `U·A·DD·24/3412` and populates each
  window's `annual_heat_loss_kwh` (winter) and the conductive part of
  `annual_heat_gain_kwh` (summer) — previously hard-coded to 0.
- **Peak heat gain** uses an orientation-specific design irradiance (west
  highest, north lowest) instead of a single flat value.
- Wall/roof and operating inputs are **captured, echoed, and audited** but do
  not alter the solar-driven savings figure — the physics-lite estimator only
  claims what it can defend.

**EnergyPlus engine** (spec Ch 4–5; PR #3): the full envelope and schedule drive
the simulation directly — wall/roof `Construction` + `Material` U-factors,
`SurfaceProperty` solar absorptance, `People`/`Lights`/`ElectricEquipment` and
`RunPeriod`/schedule objects, and the rated coil COP.

## 5. Audit defensibility (Ch 2.5)

`ProjectComparison.building` carries the full `ResolvedBuilding` (values +
provenance) into the results payload, the branded report's Inputs page, and the
audit bundle, so a reviewer can see exactly which inputs were field-measured vs.
defaulted. User-supplied U-factors/COP should be sourced (nameplate or audit)
for bid-grade defensibility.

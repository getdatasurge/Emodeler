# EnergyModeler — Architecture & Math, in plain language

This document is the operator's guide to what every part of EnergyModeler does
and **why** it does it. The goal: when an ESCO partner asks "where does the
$6,150 / yr number come from?" you can answer at any level of detail without
running a building simulation yourself.

If you only read one section, read [How a number gets to the
screen](#how-a-number-gets-to-the-screen).

---

## What the platform does, in one paragraph

A 3M dealer (or ESCO) hands you a building address and a window survey. You
pick one to three 3M films as candidates. EnergyModeler runs the **same
EnergyPlus simulation that the DOE / utility / LEED reviewer would run** on a
prototype building matched to that address's climate zone, swaps the windows
to the candidate films, and reports the kWh, $/yr, peak demand, CO₂, payback,
IRR, and 15-year NPV for each film. The audit bundle that comes with it
documents every input + standard it relied on, hashed so a reviewer can
verify the artifacts independently.

---

## How a number gets to the screen

The whole pipeline, from "user clicks Run Analysis" to "$6,150/yr appears":

```
┌─────────────────┐
│ Browser (Vite)  │ user picks films + cost, hits "Run Analysis"
└─────────┬───────┘
          │  POST /api/calc/run
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI dispatcher (backend/app/routers/calc.py)                │
│  - require_auth (Identity from JWT, or beta dev identity)       │
│  - validate project.faces / scenarios                           │
│  - create a CalculationJob row, enqueue background task         │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ pipeline.run_job (backend/app/pipeline.py)                       │
│  - load Project -> EngineProject                                │
│  - call runner.run_project                                      │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ runner.run_project (backend/energy_modeler/engine/runner.py)    │
│                                                                 │
│  if EnergyPlus binary present:                                  │
│     parser_bridge.run_real_pipeline   ── (the bid-grade path)   │
│  else:                                                          │
│     estimate.run_project              ── (the analytical fallback)
│                                                                 │
│  catches any error from the real path, falls back to estimate   │
│  with the cause attached as a warning                           │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ parser_bridge.run_real_pipeline                                  │
│                                                                 │
│  for label in [baseline, Good, Better, Best (+ Appendix G)]:    │
│     1. load the DOE prototype IDF for (building_type, CZ)       │
│     2. swap windows -> film construction (per cardinal)         │
│     3. pin HVAC COP / fan kW-CFM / economizer / daylighting     │
│     4. save IDF to /tmp/<scenario>/                             │
│     5. invoke `energyplus` binary against the TMY3 .epw         │
│     6. parse eplustbl.csv -> annual end-uses (kWh)              │
│     7. parse eplusout.csv -> per-window transmitted solar       │
│                                                                 │
│  scale every run to the project's actual size (floor or         │
│  glazing ratio) and stamp BOTH factors onto each run's warnings │
│                                                                 │
│  return (mode, baseline_run, [film_runs], appG_run)             │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ results.build_comparison                                         │
│  - delta_cooling, delta_heating, delta_lighting, delta_total kWh
│  - delta_cost = delta_elec*rate_kWh + delta_gas/29.3*rate_therm │
│  - + demand-charge component when enabled                       │
│  - payback / NPV / IRR via economics module                     │
│  - CO2 via carbon.lb_co2_avoided + co2e_kg_avoided              │
│  - Appendix G PCI: pct vs the prescriptive baseline run         │
│  → ProjectComparison                                             │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ pipeline.build_audit_bundle                                      │
│  - dump IDFs + METHODOLOGY.txt + CITATIONS.md + results.json    │
│  - compute MANIFEST.sha256 across every artifact                │
│  - zip + upload to R2 (or keep local)                           │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Frontend ResultsDashboard reads comparison via /api/jobs/{id}   │
│ - EngineModeBadge (EnergyPlus / Analytical estimate)            │
│ - WarningsList (every run's warnings, classified by severity)   │
│ - data-sanity checks (zero baseline cooling, etc.)              │
│ - top tiles + bars + tables + DataSources                       │
│ - LEED PCI anchor card when Appendix G ran                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## The two engines

### 1. EnergyPlus (bid-grade)

When the worker image has the EnergyPlus binary (the live deploy does), every
scenario is a real whole-building simulation:

- **Engine**: EnergyPlus 22.1.0, **the unmodified NREL/DOE binary**, so we
  inherit DOE's ASHRAE 140 validation.
- **Prototype**: the DOE Commercial Prototype Buildings (PNNL, energycodes.gov),
  ASHRAE 90.1-2019 edition. One per (building_type × climate_zone) pair.
- **Weather**: the TMY3 .epw matched to the project's ZIP via the climate
  zone's representative city.
- **Glazing optics**: the IGSDB-measured film records (NFRC 200 procedure).
  EnergyPlus solves the angular SHGC per timestep — there is no "single SHGC"
  number used anywhere on this path. That's the rule 3M itself publishes
  (`docs/EFILM_CROSSCHECK.md` cites it).

The pipeline is `engine/parser_bridge.py:run_real_pipeline`.

### 2. Analytical estimate (the labeled fallback)

When the EnergyPlus binary is unavailable — local dev, preview deploys, or a
provisioning failure — the pipeline degrades to a labeled analytical estimate
in `engine/estimate.py`. **Every result from this path is stamped with
`engine_mode: analytical_estimate`** and warned as "NOT for bid use". The
math:

- Baseline kWh = `nominal_eui_kWh_per_sf × gross_floor_area × operating_hours_factor`
- Cooling savings ≈ `Σ_face (POA × area × ΔSHGC) × cooling_pickup / (COP × seasonal_derate)`
- Heating, fans, lighting scaled proportionally
- Carbon and economics use the same modules as the EnergyPlus path

It's calibrated against 3M dealer Excel benchmarks but is **not** a bid-grade
result. The UI's `EngineModeBadge` makes this distinction obvious.

---

## How we mutate the DOE prototype for a film run

The DOE prototype is ~10,000 lines of IDF. We change the minimum needed:

| What we change | Why | Helper |
|---|---|---|
| Window `Construction` (per cardinal) | The actual film effect | `idf_ops.set_window_construction_by_orientation` |
| `Coil:Cooling:DX:*.COP` | Match the project's as-built COP | `idf_ops.set_cooling_cop` |
| `Coil:Heating:DX:*.COP` | Same for heating | `idf_ops.set_heating_cop` |
| `Fan:*.Pressure_Rise` | Project's measured fan kW/CFM | `idf_ops.set_fan_kw_per_cfm` |
| `Controller:OutdoorAir.Economizer_*` | Switch NoEconomizer → FixedDryBulb at user limit | `idf_ops.set_economizer_high_limit_f` |
| `Daylighting:Controls` (opt-in) | Model the lighting uptick from a low-VT film | `idf_ops.add_daylighting_controls` |
| `Output:Diagnostics` | Silence the 10M-line shading-tessellation warning storm | `idf_ops.quiet_diagnostics` |
| `Output:Variable / Output:Meter` | Add the variables our parser reads | `idf_ops.add_standard_outputs` |

The prototype geometry / zones / HVAC topology / schedules are otherwise
untouched. That's deliberate — the inheritance of DOE's validation depends on
the binary running an unmodified prototype.

### Glazing per cardinal direction

When a building has tinted south + clear elsewhere, the dealer Excel
collapses to one number. The platform doesn't:

1. `parser_bridge._glazings_by_cardinal` reads every `EngineFace`, gives
   intercardinals (SE / SW / NE / NW) half-area each to the two adjacent
   cardinals, and picks the area-weighted dominant glazing per cardinal.
2. `idf_builder.build_scenario_idf` builds one `WindowMaterial:Glazing`-based
   `Construction` per direction.
3. `idf_ops.set_window_construction_by_orientation` walks every
   `FenestrationSurface:Detailed` window and assigns it the construction
   matching its elevation (parsed from the surface Name token —
   `..._Wall_South_Window1` → `S`).
4. A `DEFAULT` construction catches windows whose elevation can't be
   inferred (skylights, anonymous surfaces).

---

## Scaling the prototype to the project's actual size

The DOE prototype is built at its **nominal** floor area
(~53,628 sf for MediumOffice). The user's project is almost never that exact
size. Without rescaling, the absolute energies / savings / peak demand belong
to the prototype, not the project — a reviewer would catch that in the first
question.

Two scale factors, both stamped on every run's `warnings` regardless of
which is applied:

| Basis | Formula | When to use |
|---|---|---|
| `floor` (default, matches EFILM) | `project_floor_sf / prototype_floor_sf` | Reviewer comparing against an EFILM dealer Excel |
| `glazing` | `Σ face.area_sqft / prototype_glazing_sf` | A building whose glazing-to-floor ratio diverges from the prototype's |

Prototype glazing area is derived from `nominal_area_sf`, `floors`, and the
prototype's `wwr` (window-to-wall ratio) using a square-footprint geometry —
the same assumption `engine/building.py` uses for the analytical fallback,
so the two paths stay consistent.

`parser_bridge._scale_run` multiplies:

- every kWh end-use field
- cooling peak kW + total facility peak kW
- monthly cooling profile (12 values)
- per-orientation transmitted-solar aggregates

by the active factor. The factor is recorded in the audit so PCI / EFILM
reviewers see the math.

---

## The 8-point compass

Surveyors record window orientation at the intercardinals (`NE`, `SE`, `SW`,
`NW`) on the 3M / IWFA survey sheet. The platform now honours that:

- The API regex (`schemas_api.FaceIn.orientation`) accepts the full 8-point
  set + `H` (skylight).
- `engine.weather.FACE_GEOMETRY` maps each face to its (tilt°, azimuth°)
  pair in PVWatts convention (`0=N`, `90=E`, `180=S`, `270=W`).
- `engine.building.PEAK_POA_W_M2` has design-peak irradiance per face;
  `SW` is pinned close to `W` because both share the afternoon cooling
  system peak.
- The offline POA fallback synthesises each intercardinal as the per-month
  average of its two adjacent cardinals. When `NREL_API_KEY` is set, PVWatts
  returns the exact azimuth — those responses are cached per
  (lat, lon, tilt, azimuth) so the 8-point compass doesn't double the API
  call count.

---

## Gas vs electric pricing

The MediumOffice prototype heats partly with natural gas. Before this round
of work, **all** dollar savings were priced at the electric rate, so a
gas-heated office's $/yr was materially wrong.

```
delta_cost_usd_per_year
  = delta_total_elec_kWh × utility_rate_usd_kWh
  + delta_gas_kWh / 29.3001 × gas_rate_usd_therm   ← new
  + demand_savings (when demand_charge_usd_per_kw set)
```

`29.3001 kWh = 1 therm` (100,000 BTU). When `gas_rate_usd_therm` is unset,
the gas contribution stays at $0 — that matches the prior all-electric
behaviour. `FilmComparison.delta_gas_kwh` is still on the wire so a
reviewer sees the therm swing even when there's no priced rate.

---

## Appendix G baseline (LEED PCI)

LEED EAc credits compare your **proposed** building against an **ASHRAE
90.1-2019 Appendix G prescriptive baseline**. When
`CalcOptions.include_appendix_g_baseline=true`:

1. `engine.appendix_g.baseline_spec(building_type, climate_zone, floors,
   area_sf)` resolves the prescriptive numbers from Tables G3.4 / G3.5 /
   G3.1.1 / G3.1.6 — the per-CZ window U and SHGC, opaque wall + roof U,
   lighting power density, and the baseline HVAC system call.
2. `engine.appendix_g.build_baseline_idf` writes a `SimpleGlazingSystem`
   window at those prescriptive numbers, plus baseline LPD on every
   `Lights` object.
3. `parser_bridge.run_real_pipeline` runs it as the 4th scenario.
4. `results.build_comparison` returns:

   ```
   pct_savings_vs_code_baseline       = (appG.total_elec − project.total_elec) / appG.total_elec
   cooling_pct_savings_vs_code_baseline = same for cooling
   ```

5. `CITATIONS.md` per run stamps the prescriptive U/SHGC values used.
6. The dashboard renders an `AppendixGCard` showing both pcts.

PCI = ~the cooling number when window-films are the only ECM.

---

## The audit bundle

Every run produces `<storage>/<job_id>/audit_bundle_<job_id>.zip` containing:

| File | What it is |
|---|---|
| `idf/baseline.idf` + `idf/<scenario>.idf` | The actual IDF the simulator ran (or would have run, on the analytical path) |
| `results.json` | Full `ProjectComparison` payload |
| `METHODOLOGY.txt` | Engine + prototype + weather + glazing-optics + carbon + standards block |
| `CITATIONS.md` | Per-run citation of every upstream standard with the exact source identifier (climate-zone, weather station, glazing IGSDB IDs, EPA eGRID subregion, scaling-basis used, LEED PCI numbers when Appendix G ran) |
| `MANIFEST.sha256` | `sha256sum -c`-compatible list — `<hash>  <relative-path>` per file, lets a reviewer verify any artifact independently |

If `R2_*` env vars are set, the zip also lands in Cloudflare R2 and the
audit-bundle URL becomes a 7-day signed redirect. Otherwise it serves from
the persistent disk.

---

## The survey importer

3M/IWFA distributes a standardised window survey workbook. The format is
fixed; we parse it in `parser/survey_xlsx.py`.

### What the sheet contains

| Column | Used for |
|---|---|
| Building ID | Splits portfolios into one project per building |
| Floor #, Map Number, Zone | Audit trail on the resulting Face's `notes` |
| Compass | The face's `orientation` (8-point) |
| Glass Color | Maps to a `base_glazing_id` via `GLASS_COLOR_TO_GLAZING_ID` |
| GC3200 Reading | Surveyor's handheld SHGC meter; aggregated per bucket and cross-checked against the catalog SHGC |
| W, H | Window dimensions in inches; `area_sqft = W × H / 144` |

Compass + Color **fill down** between rows — the surveyor writes the
elevation + color once at the top of each block. The parser tracks
`last_compass` / `last_color` / `last_building` so blank cells inherit the
most recent value.

### Two endpoints

- `POST /api/projects/{id}/import-survey-xlsx?mode=replace|append`
  collapses all buildings into the named project (one face per
  (orientation × glazing)).
- `POST /api/projects/import-survey-portfolio?zip=&building_type=&gross_floor_area_sf=`
  splits per Building ID and **creates one Project per building** with the
  template applied. The Millstone / New Brunswick / Evesham workbook
  becomes 15 quotable projects from one upload.

### The GC3200 cross-check

The Solar Gard GC3200 is a handheld SHGC meter that surveyors use to spot-
check glazing. The parser averages every populated reading per bucket and
writes `GC3200 avg SHGC: 0.71 (n=14)` onto the face notes. When the
measured average diverges from the catalog SHGC by more than 0.06 (meter
± 0.03 plus glass-to-glass scatter), it adds:

```
REVIEW: measured SHGC 0.45 vs catalog 0.70 for dbl_clear_3mm_13mmAir
— likely mis-classified glass
```

This catches a "labeled clear but is actually reflective" mistake before
the audit shows the wrong baseline SHGC.

---

## Multi-tenancy

Every user-data table carries `org_id`. The auth dependency
(`auth.require_auth`) resolves the caller to an `Identity(user_id, org_id)`
either from the Supabase JWT (when `AUTH_ENFORCED=true`) or from the dev
identity on `DEFAULT_ORG_ID` (the beta single-tenant default).

**What's scoped:** every project / job / report / face / scenario endpoint.
A foreign org gets a 404 (not 403) so we don't leak whether the id exists.

**What's not scoped:** `/api/films`, `/api/base-glazings`, `/api/zip*` and
similar catalog endpoints — they're shared reference data.

To onboard a second ESCO dealer to the same deploy:
1. Set `AUTH_ENFORCED=true` and `SUPABASE_JWT_SECRET=...`.
2. Their Supabase project mints JWTs with `app_metadata.org_id` set.
3. They sign in; everything they create is stamped with their org.

---

## HVAC override knobs

The DOE prototype's HVAC is a placeholder; an ESCO with nameplates wants to
push their actual numbers in. Five knobs are wired:

| Field | What it does | IDF helper |
|---|---|---|
| `hvac_cooling_cop` | Rated COP on every DX cooling coil | `set_cooling_cop` |
| `hvac_heating_cop` | Rated COP on every DX heating coil | `set_heating_cop` |
| `hvac_fan_kw_per_cfm` | Scales `Pressure_Rise` on every Fan:* so power per CFM hits the target while preserving `Fan_Total_Efficiency` | `set_fan_kw_per_cfm` |
| `hvac_economizer_high_limit_f` | Flips NoEconomizer Controller:OutdoorAir → FixedDryBulb at user's F limit (richer schemes preserved) | `set_economizer_high_limit_f` |
| `add_daylighting_controls` (opt-in CalcOption) | Adds SplitFlux `Daylighting:Controls` to zones with windows but no controls | `add_daylighting_controls` |

Operating-hours-per-week drives the analytical fallback baseline EUI but
the EnergyPlus path uses the prototype's own `Schedule:Compact` objects;
that gap is documented in the run warnings.

---

## Per-window solar chart

The "Solar gain rejected by face" panel reads `RunResult.windows` —
populated by:

1. `idf_ops.add_standard_outputs` requests `Surface Window Transmitted
   Solar Radiation Energy` (Joules, monthly) as an `Output:Variable`.
2. `parser.eplus_window_solar.parse_window_transmitted_solar` reads
   `eplusout.csv`, regex-matches `<key>:Surface Window Transmitted Solar
   Radiation Energy [J](Monthly)` columns, sums to annual J, converts to kWh
   via `J / 3.6e6`.
3. `parser_bridge._attach_window_solar` aggregates per cardinal direction
   (parsed from the window Name) and stamps one `WindowSurfaceResult` per
   orientation onto each RunResult.
4. The frontend chart groups by `surface_name.split('_')[1]`.

---

## Configuration / env vars

| Env var | Default | What it does |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./energy_modeler.db` | SQLAlchemy URL. Render uses `sqlite:////data/...` on the persistent disk; prod swaps to Postgres. |
| `STORAGE_DIR` | `./storage` | Audit bundles + per-job working dirs. |
| `PROTOTYPES_DIR` | `<data>/prototypes` | DOE prototype IDFs (~150 files for 90.1-2019). |
| `ENERGYPLUS_DIR` | (auto-detect) | Where `energyplus` + `Energy+.idd` live. Falls back to PATH glob — current images install at `/usr/local/EnergyPlus-22.1.0-...`. |
| `NREL_API_KEY` | unset | Enables live PVWatts POA queries. When unset, the offline climate POA fallback is used. |
| `IGSDB_API_TOKEN` | unset | Enables live IGSDB optical lookups. Bundled records are the fallback. |
| `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | unset | Audit bundles go to Cloudflare R2 with signed URLs. Local-disk fallback otherwise. |
| `AUTH_ENFORCED` | `false` | When `true`, every request requires a Supabase JWT. |
| `SUPABASE_JWT_SECRET` | unset | HS256 secret for JWT verification. Required when `AUTH_ENFORCED=true`. |
| `SENTRY_DSN` | unset | Error tracking. No-op when unset. |
| `REDIS_URL` | unset | When set, calc jobs enqueue to the Celery worker stack instead of running inline. |

---

## Deployment — Render single-service all-in-one

The default deploy is one Render web service running `Dockerfile.allinone`:

```
nrel/energyplus:22.1.0  ──── multi-stage COPY ────►  ubuntu:22.04 + Python 3.10
                                                     + EnergyPlus 22.1 binary
                                                     + the FastAPI app
                                                     + WeasyPrint deps
                                                     + libx11-6 for E+ runtime
```

Key Render settings:
- Root Directory: `backend`
- Dockerfile Path: `backend/Dockerfile.allinone`
- Persistent disk mounted at `/data` — survives redeploys
- Env vars set per the table above
- Build hook runs `scripts/fetch_prototypes.py` + `scripts/fetch_weather.py`
  to populate `/data/prototypes` and `/data/storage/weather`

For throughput, `docker-compose --profile full` swaps in the worker /
Redis / API stack instead. `Dockerfile.worker` is the Celery worker image.

---

## Standards & citations — what each run cites

`CITATIONS.md` per audit bundle names every upstream standard with the
exact source identifier used:

| Layer | Reference |
|---|---|
| Engine | EnergyPlus 22.1.0 (NREL/DOE, unmodified) — inherits DOE's ASHRAE 140 validation |
| Prototype | DOE Commercial Prototype Buildings, ASHRAE 90.1-2019 (PNNL, energycodes.gov) |
| Weather | TMY3 .epw, energycodes.gov IECC bundle |
| Glazing optics | LBNL IGSDB (3M monolithic glass+film records, NFRC 200 procedure) |
| Carbon | EPA eGRID 2023, subregion total output emissions rates |
| Heat balance | ISO 15099 §8.3.2.2 (interior convection); EnergyPlus Engineering Reference, Window Calculation Module |
| Angular optics | 3M spec §2.1 — never single-SHGC; E+ solves T(θ)/R(θ)/A(θ) per timestep |

---

## Testing strategy

```
$ pytest -q
136 passed, 2 skipped
```

| Test file | What it covers |
|---|---|
| `test_engine.py` | Spec §12.1 FX-01 / FX-02 / FX-03 fixtures + window-conduction sanity |
| `test_appendix_g.py` | Baseline-spec lookups |
| `test_appendix_g_wiring.py` | Plumbed Appendix G run through the comparison |
| `test_parser.py` | eplustbl.csv parser (real format, GJ → kWh, substring trap) |
| `test_window_solar.py` | Per-window transmitted-solar parser + aggregation |
| `test_parser_bridge_scaling.py` | Floor + glazing scale factors |
| `test_per_face_glazing.py` | Per-cardinal glazing dispatch |
| `test_face_tilt.py` | tilt_deg round-trip and clamping |
| `test_operating_hours.py` | Operating-hours analytical scaling |
| `test_gas_pricing.py` | Heating-gas savings priced at $/therm |
| `test_hvac_fan.py` | Fan kW/CFM + economizer high-limit + quiet diagnostics |
| `test_daylighting_controls.py` | Opt-in daylighting injector |
| `test_survey_xlsx.py` | Survey parser: fill-down, in→ft, color → glazing, building dimension, collapse, notes capture, GC3200 |
| `test_multi_tenancy.py` | Org-scope on every project / job / report endpoint |
| `test_runner_errors.py` | EnergyPlus failure surface (no silent fall to estimate) |
| `test_audit_bundle.py` | Manifest hash + citations + write end-to-end |
| `test_api.py` | API smoke + happy path |
| `test_models.py` | ORM mapping |
| `test_carbon.py` / `test_economics.py` / `test_leed.py` | Pure math modules |

Two skips are EnergyPlus-dependent IDF tests that only run on the worker
image; the rest exercise pure Python.

---

## Known limitations (called out in the run warnings)

1. **Operating-hours don't yet drive the EnergyPlus path.** The field
   adjusts the analytical fallback baseline EUI; the EnergyPlus path uses
   the prototype's `Schedule:Compact` objects unchanged.
2. **`tilt_deg` is informational on the EnergyPlus path.** The audit
   records what the user said, but the prototype's window vertices aren't
   mutated — closing this needs `geomeppy` for geometry mutation, which is
   blocked on the shapely + matplotlib build deps we dropped to get the
   worker image building.
3. **Migration story is a startup shim.** `db._apply_pending_columns`
   ALTER TABLE ADD COLUMNs the new columns idempotently. Fine for the
   schema's current churn rate; replace with Alembic once the schema
   settles.
4. **Daylighting reference points are generic.** When
   `add_daylighting_controls` runs, the reference point lands at
   `zone_origin + (1.5m, 1.5m, 0.76m)` — accurate-enough for the "daylit
   zone" signal but not a zone-centroid placement.

---

## Glossary

- **POA** — Plane of Array. Solar irradiance on a tilted surface (W/m²).
- **SHGC** — Solar Heat Gain Coefficient. The fraction of incident solar
  energy that ends up as heat inside (0.0–1.0).
- **VT** — Visible Transmittance. The fraction of visible light that
  passes through (0.0–1.0).
- **U-factor** — Conductive heat transfer coefficient (BTU/h·ft²·°F).
- **WWR** — Window-to-Wall Ratio. Glazing area ÷ exterior wall area.
- **EUI** — Energy Use Intensity (kWh/ft²/yr).
- **PCI** — Performance Cost Index. LEED EAc metric — proposed energy as a
  % of the Appendix G baseline.
- **COP** — Coefficient of Performance. Cooling/heating output ÷ input.
- **eGRID** — EPA's Emissions & Generation Resource Integrated Database.
  Source of carbon-intensity factors by power-grid subregion.
- **TMY3** — Typical Meteorological Year 3. The hourly weather file format
  EnergyPlus consumes.
- **IGSDB** — International Glazing Database (LBNL). Source of measured
  glass + film optical records.
- **NFRC** — National Fenestration Rating Council. Procedures that
  certify the glazing optical numbers we cite.

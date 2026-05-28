-- EnergyModeler — canonical Postgres / Supabase schema (spec Ch 9.3).
-- The beta runs on SQLite via the SQLAlchemy ORM (app/models.py); this file is
-- the production DDL and the source of truth for the Supabase migration.
-- Every user-data table carries org_id so the Phase 4 multi-tenant switch is an
-- RLS policy activation, not a schema change.

-- ========== auth & orgs ==========
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id          UUID PRIMARY KEY REFERENCES auth.users(id),
    org_id      UUID NOT NULL REFERENCES organizations(id),
    email       TEXT NOT NULL UNIQUE,
    full_name   TEXT,
    role        TEXT NOT NULL DEFAULT 'analyst',  -- owner | admin | analyst | viewer
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========== reference catalog ==========
CREATE TABLE films (
    sku                  TEXT PRIMARY KEY,
    product_line         TEXT NOT NULL,
    display_name         TEXT NOT NULL,
    igsdb_product_id     INTEGER NOT NULL,
    igsdb_record_synced  TIMESTAMPTZ,
    cached_optical       JSONB,
    tvis_pct             NUMERIC(4,1) NOT NULL,
    shgc_on_dbl_clear    NUMERIC(4,3) NOT NULL,
    uv_block_pct         NUMERIC(4,1),
    warranty_yrs         INTEGER,
    thickness_mil        NUMERIC(4,1),
    list_price_per_sqft  NUMERIC(8,2),
    dealer_cost_per_sqft NUMERIC(8,2),
    is_active            BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE base_glazings (
    id                  TEXT PRIMARY KEY,
    display_name        TEXT NOT NULL,
    description         TEXT,
    layer_count         SMALLINT NOT NULL,
    u_factor_btuhrft2F  NUMERIC(5,3) NOT NULL,
    shgc                NUMERIC(4,3) NOT NULL,
    vt                  NUMERIC(4,3) NOT NULL,
    igsdb_construction  JSONB NOT NULL
);

CREATE TABLE film_glass_pairings (
    film_sku        TEXT NOT NULL REFERENCES films(sku),
    base_glass_id   TEXT NOT NULL REFERENCES base_glazings(id),
    shgc            NUMERIC(4,3) NOT NULL,
    u_btu_h_ft2_F   NUMERIC(5,3) NOT NULL,
    vt              NUMERIC(4,3) NOT NULL,
    source          TEXT NOT NULL,          -- igsdb | lbnl_window_8_local | manufacturer
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (film_sku, base_glass_id)
);

-- ========== projects & geometry ==========
CREATE TABLE projects (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id               UUID NOT NULL REFERENCES organizations(id),
    created_by           UUID REFERENCES users(id),
    name                 TEXT NOT NULL,
    customer_name        TEXT,
    address_line1        TEXT,
    city                 TEXT,
    state                TEXT,
    zip                  TEXT NOT NULL,
    latitude             NUMERIC(8,5),
    longitude            NUMERIC(8,5),
    climate_zone         TEXT NOT NULL,
    building_type        TEXT NOT NULL,
    gross_floor_area_sf  NUMERIC(12,1) NOT NULL,
    utility_label        TEXT,
    utility_rate_usd_kwh NUMERIC(7,5) NOT NULL,
    utility_rate_source  TEXT NOT NULL,      -- urdb | user_override
    egrid_subregion      TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'draft',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_projects_org ON projects(org_id);

CREATE TABLE faces (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    orientation     CHAR(1) NOT NULL,        -- N S E W H
    area_sqft       NUMERIC(10,2) NOT NULL,
    base_glazing_id TEXT NOT NULL REFERENCES base_glazings(id),
    count           INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE scenarios (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    label                   TEXT NOT NULL,
    film_sku                TEXT NOT NULL REFERENCES films(sku),
    installed_cost_usd      NUMERIC(12,2) NOT NULL,
    installed_cost_per_sqft NUMERIC(8,2),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========== calculation runs & results ==========
CREATE TABLE calculation_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status              TEXT NOT NULL,       -- queued | running | completed | failed
    engine_mode         TEXT,                -- energyplus | analytical_estimate
    energyplus_version  TEXT,
    weather_station     TEXT,
    weather_dataset     TEXT,
    baseline_run_id     UUID,
    audit_bundle_url    TEXT,
    error_message       TEXT,
    error_phase         TEXT,
    options             JSONB,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE scenario_results (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                 UUID NOT NULL REFERENCES calculation_jobs(id) ON DELETE CASCADE,
    scenario_id            UUID REFERENCES scenarios(id),  -- NULL for baseline
    is_baseline            BOOLEAN NOT NULL DEFAULT FALSE,
    is_appendix_g_baseline BOOLEAN NOT NULL DEFAULT FALSE,
    annual_end_uses        JSONB NOT NULL,
    peak_demand            JSONB NOT NULL,
    windows                JSONB NOT NULL,
    delta_total_kwh        NUMERIC(12,2),
    delta_cooling_kwh      NUMERIC(12,2),
    delta_heating_kwh      NUMERIC(12,2),
    delta_peak_kw          NUMERIC(8,3),
    delta_cost_usd_yr      NUMERIC(10,2),
    delta_co2_lb_yr        NUMERIC(12,1),
    simple_payback_yrs     NUMERIC(6,2),
    npv_15yr_usd           NUMERIC(12,2),
    irr_15yr_pct           NUMERIC(6,3),
    raw_eplus_output_url   TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========== audit trail ==========
CREATE TABLE film_record_history (
    id                BIGSERIAL PRIMARY KEY,
    film_sku          TEXT NOT NULL REFERENCES films(sku),
    igsdb_product_id  INTEGER NOT NULL,
    fetched_at        TIMESTAMPTZ NOT NULL,
    changed           BOOLEAN NOT NULL,
    diff_summary      JSONB
);

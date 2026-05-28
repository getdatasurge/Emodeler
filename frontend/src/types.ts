// API response/request types for the EnergyModeler backend.
// Shapes verified against the live FastAPI responses.

export interface Meta {
  version: string;
  engine_mode: string; // 'energyplus' | 'analytical_estimate'
  energyplus_available: boolean;
  nrel_live: boolean;
  igsdb_live: boolean;
  notice: string | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  customer_name: string | null;
  zip: string;
  building_type: string;
  status: string;
  climate_zone: string | null;
}

export interface Face {
  id: string;
  orientation: string; // N | S | E | W | H
  area_sqft: number;
  base_glazing_id: string;
  count: number;
  notes: string | null;
}

export interface ScenarioStored {
  id: string;
  label: string;
  film_sku: string;
  installed_cost_usd: number;
}

// Optional as-built building characterization (spec Ch 5.3). Blank values fall
// back to prototype / climate-zone defaults at calc time.
export interface BuildingInputs {
  hvac_cooling_cop?: number | null;
  hvac_heating_cop?: number | null;
  hvac_system_type?: string | null;
  wall_area_sf?: number | null;
  wall_u_factor?: number | null;
  wall_absorptance?: number | null;
  roof_area_sf?: number | null;
  roof_type?: string | null;
  roof_u_factor?: number | null;
  roof_absorptance?: number | null;
  operating_hours_per_week?: number | null;
  num_floors?: number | null;
  floor_to_floor_ft?: number | null;
}

export interface Project extends BuildingInputs {
  id: string;
  name: string;
  customer_name: string | null;
  address_line1: string | null;
  city: string | null;
  state: string | null;
  zip: string;
  latitude: number | null;
  longitude: number | null;
  climate_zone: string | null;
  building_type: string;
  gross_floor_area_sf: number;
  utility_label: string | null;
  utility_rate_usd_kwh: number | null;
  utility_rate_source: string | null;
  egrid_subregion: string | null;
  status: string;
  faces: Face[];
  scenarios: ScenarioStored[];
}

export interface FaceInput {
  orientation: string;
  area_sqft: number;
  base_glazing_id: string;
  count: number;
  notes?: string | null;
}

export interface ScenarioInput {
  label: string;
  film_sku: string;
  installed_cost_usd: number;
}

export interface ProjectCreate extends BuildingInputs {
  name: string;
  customer_name?: string | null;
  address_line1?: string | null;
  city?: string | null;
  state?: string | null;
  zip: string;
  building_type: string;
  gross_floor_area_sf: number;
  climate_zone?: string | null;
  utility_rate_usd_kwh?: number | null;
  egrid_subregion?: string | null;
  faces?: FaceInput[];
  scenarios?: ScenarioInput[];
}

export interface ClimateZone {
  zip: string;
  climate_zone: string;
  lat: number;
  lon: number;
  station_id: string;
  station_city: string;
}

export interface Egrid {
  zip: string;
  subregion: string;
  subregion_name: string;
  co2_lb_per_mwh: number;
  co2e_lb_per_mwh: number;
  source: string;
}

export interface Utility {
  zip: string;
  default_utility: string | null;
  urdb_label: string | null;
  rate_name: string | null;
  avg_energy_rate_usd_kwh: number;
  has_time_of_use: boolean;
  has_demand_charges: boolean;
  source: string;
}

export interface Film {
  sku: string;
  product_line: string;
  display_name: string;
  igsdb_product_id: number;
  tvis_pct: number;
  shgc_on_dbl_clear: number;
  uv_block_pct: number;
  warranty_yrs: number;
  thickness_mil: number;
  list_price_per_sqft: number;
  is_active: boolean;
}

export interface BaseGlazing {
  id: string;
  display_name: string;
  description: string;
  layer_count: number;
  u_factor_btuhrft2F: number;
  shgc: number;
  vt: number;
  igsdb_construction: (number | string)[];
}

export interface Pairing {
  film_sku: string;
  base_glazing_id: string;
  shgc: number;
  u_btu_h_ft2_F: number;
  vt: number;
  base_shgc: number;
  source: string;
}

export interface CalcOptions {
  film_life_yrs: number;
  discount_rate: number;
  utility_escalation: number;
}

export interface CalcRunRequest {
  project_id: string;
  scenarios: ScenarioInput[];
  options: CalcOptions;
}

export interface CalcRunResponse {
  job_id: string;
  status: string;
  estimated_runtime_sec: number;
  poll_url: string;
}

export interface ScenarioResult {
  scenario_label: string;
  film_sku: string;
  delta_cooling_kwh: number;
  delta_heating_kwh: number;
  delta_lighting_kwh: number;
  delta_total_kwh: number;
  delta_peak_kw: number;
  delta_cost_usd_per_year: number;
  delta_co2_lb_per_year: number;
  project_cost_usd: number;
  simple_payback_years: number; // -1 == n/a
  npv_15yr_usd: number;
  irr_15yr_pct: number; // -1 == n/a
}

export interface JobProgress {
  scenarios_completed: number;
  scenarios_total: number;
}

// /api/jobs/{id} is a discriminated union on `status`.
export interface JobRunning {
  job_id: string;
  status: 'running' | 'queued';
  progress?: JobProgress;
}

export interface JobFailed {
  job_id: string;
  status: 'failed';
  error_message: string | null;
  error_phase: string | null;
}

export interface JobCompleted {
  job_id: string;
  status: 'completed';
  engine_mode: string;
  completed_at: string | null;
  results_url: string;
  audit_bundle_url: string;
  warnings: string[];
  baseline: unknown;
  scenario_results: ScenarioResult[];
}

export type Job = JobRunning | JobFailed | JobCompleted;

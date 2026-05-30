import { useState } from 'react';
import { api, ApiError } from '../api';
import type { ClimateZone, Egrid, Project, Utility } from '../types';
import {
  Button,
  Card,
  ErrorBox,
  Label,
  Select,
  SectionTitle,
  Spinner,
  TextInput,
} from '../components/ui';

const BUILDING_TYPES = [
  'SmallOffice',
  'MediumOffice',
  'LargeOffice',
  'PrimarySchool',
  'SecondarySchool',
  'StandaloneRetail',
  'StripMall',
  'Warehouse',
];

export function ProjectIntake({
  onCreated,
  onCancel,
}: {
  onCreated: (project: Project) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState('');
  const [customer, setCustomer] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [zip, setZip] = useState('');
  const [buildingType, setBuildingType] = useState('MediumOffice');
  const [grossArea, setGrossArea] = useState('');

  // ZIP-derived auto-fill.
  const [climate, setClimate] = useState<ClimateZone | null>(null);
  const [egrid, setEgrid] = useState<Egrid | null>(null);
  const [utility, setUtility] = useState<Utility | null>(null);
  const [rate, setRate] = useState('');
  const [rateEdited, setRateEdited] = useState(false);
  const [gasRate, setGasRate] = useState('');
  const [zipLoading, setZipLoading] = useState(false);
  const [zipError, setZipError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Optional as-built building characterization. Blank = use prototype default.
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [adv, setAdv] = useState<Record<string, string>>({});
  const setAdvField =
    (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setAdv((p) => ({ ...p, [k]: e.target.value }));

  const ADV_NUM_FIELDS = [
    'hvac_cooling_cop', 'hvac_heating_cop', 'hvac_fan_kw_per_cfm',
    'wall_area_sf', 'wall_u_factor',
    'wall_absorptance', 'roof_area_sf', 'roof_u_factor', 'roof_absorptance',
    'operating_hours_per_week', 'num_floors', 'floor_to_floor_ft',
  ];
  const ADV_STR_FIELDS = ['hvac_system_type', 'roof_type'];

  function advPayload(): Record<string, number | string> {
    const out: Record<string, number | string> = {};
    for (const k of ADV_NUM_FIELDS) {
      const v = adv[k]?.trim();
      if (v) out[k] = Number(v);
    }
    for (const k of ADV_STR_FIELDS) {
      const v = adv[k]?.trim();
      if (v) out[k] = v;
    }
    return out;
  }

  function advNum(k: string, label: string, ph: string, step = 'any') {
    return (
      <div>
        <Label>{label}</Label>
        <TextInput
          type="number"
          step={step}
          value={adv[k] ?? ''}
          onChange={setAdvField(k)}
          placeholder={ph}
        />
      </div>
    );
  }

  async function handleZipBlur() {
    if (!zip || zip.length < 5) return;
    setZipLoading(true);
    setZipError(null);
    setClimate(null);
    setEgrid(null);
    setUtility(null);
    try {
      const [cz, eg, ut] = await Promise.all([
        api.climateZone(zip).catch((e) => {
          // Climate zone 404 means the ZIP isn't in the crosswalk — surface it.
          throw e;
        }),
        api.egrid(zip),
        api.utility(zip),
      ]);
      setClimate(cz);
      setEgrid(eg);
      setUtility(ut);
      if (!rateEdited) {
        setRate(String(ut.avg_energy_rate_usd_kwh));
      }
    } catch (e) {
      const msg =
        e instanceof ApiError && e.status === 404
          ? `ZIP ${zip} is not in the bundled climate crosswalk.`
          : (e as Error).message;
      setZipError(msg);
    } finally {
      setZipLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    if (!name || !zip || !grossArea) {
      setSubmitError('Name, ZIP, and gross floor area are required.');
      return;
    }
    setSubmitting(true);
    try {
      const project = await api.createProject({
        name,
        customer_name: customer || null,
        address_line1: address || null,
        city: city || null,
        state: state || null,
        zip,
        building_type: buildingType,
        gross_floor_area_sf: Number(grossArea),
        climate_zone: climate?.climate_zone ?? null,
        egrid_subregion: egrid?.subregion ?? null,
        utility_rate_usd_kwh: rateEdited && rate ? Number(rate) : null,
        gas_rate_usd_therm: gasRate ? Number(gasRate) : null,
        ...advPayload(),
      });
      onCreated(project);
    } catch (e) {
      setSubmitError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <button
        onClick={onCancel}
        className="mb-4 text-sm text-ink/60 hover:text-ink"
      >
        &larr; Back to projects
      </button>
      <h1 className="mb-6 text-2xl font-bold text-ink">New Project</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <SectionTitle>Project details</SectionTitle>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label>Project name *</Label>
              <TextInput
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Riverside Office Retrofit"
              />
            </div>
            <div>
              <Label>Customer name</Label>
              <TextInput
                value={customer}
                onChange={(e) => setCustomer(e.target.value)}
              />
            </div>
            <div>
              <Label>Building type</Label>
              <Select
                value={buildingType}
                onChange={(e) => setBuildingType(e.target.value)}
              >
                {BUILDING_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            </div>
            <div className="sm:col-span-2">
              <Label>Address</Label>
              <TextInput
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </div>
            <div>
              <Label>City</Label>
              <TextInput value={city} onChange={(e) => setCity(e.target.value)} />
            </div>
            <div>
              <Label>State</Label>
              <TextInput
                value={state}
                onChange={(e) => setState(e.target.value)}
                maxLength={2}
              />
            </div>
            <div>
              <Label>ZIP *</Label>
              <TextInput
                value={zip}
                onChange={(e) => setZip(e.target.value)}
                onBlur={handleZipBlur}
                placeholder="33540"
              />
            </div>
            <div>
              <Label>Gross floor area (sf) *</Label>
              <TextInput
                type="number"
                value={grossArea}
                onChange={(e) => setGrossArea(e.target.value)}
                placeholder="14500"
              />
            </div>
          </div>
        </Card>

        <Card>
          <SectionTitle>Location data (auto-filled from ZIP)</SectionTitle>
          {zipLoading && <Spinner label="Looking up ZIP…" />}
          {zipError && <ErrorBox message={zipError} />}
          {!zipLoading && !zipError && !climate && (
            <p className="text-sm text-ink/60">
              Enter a ZIP and click away to auto-fill climate zone, grid
              subregion, and utility rate.
            </p>
          )}
          {climate && (
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <Label>Climate zone</Label>
                <div className="rounded-md bg-neutralbg px-3 py-2 text-sm font-medium text-ink">
                  {climate.climate_zone}
                  <span className="ml-2 text-xs text-ink/50">
                    {climate.station_city}
                  </span>
                </div>
              </div>
              <div>
                <Label>eGRID subregion</Label>
                <div className="rounded-md bg-neutralbg px-3 py-2 text-sm font-medium text-ink">
                  {egrid?.subregion ?? '—'}
                  {egrid && (
                    <span className="ml-2 text-xs text-ink/50">
                      {egrid.subregion_name}
                    </span>
                  )}
                </div>
              </div>
              <div>
                <Label>Utility rate ($/kWh)</Label>
                <TextInput
                  type="number"
                  step="0.0001"
                  value={rate}
                  onChange={(e) => {
                    setRate(e.target.value);
                    setRateEdited(true);
                  }}
                />
                {utility && (
                  <p className="mt-1 text-xs text-ink/50">{utility.source}</p>
                )}
              </div>
              <div>
                <Label>Gas rate ($/therm, optional)</Label>
                <TextInput
                  type="number"
                  step="0.01"
                  value={gasRate}
                  onChange={(e) => setGasRate(e.target.value)}
                  placeholder="e.g. 1.20"
                />
                <p className="mt-1 text-xs text-ink/50">
                  Required for accurate dollar savings on gas-heated buildings;
                  leave blank for all-electric projects.
                </p>
              </div>
            </div>
          )}
        </Card>

        <Card>
          <button
            type="button"
            onClick={() => setShowAdvanced((s) => !s)}
            className="flex w-full items-center justify-between text-left"
          >
            <SectionTitle>Building details (advanced)</SectionTitle>
            <span className="text-sm text-ink/50">{showAdvanced ? '–' : '+'}</span>
          </button>
          <p className="-mt-1 mb-3 text-xs text-ink/50">
            Optional. Leave blank to use the DOE prototype &amp; ASHRAE 90.1
            climate-zone defaults. Supplying the as-built HVAC efficiency and
            envelope sharpens the estimate (and feeds the EnergyPlus engine).
          </p>
          {showAdvanced && (
            <div className="space-y-5">
              <div>
                <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-ink/50">
                  HVAC
                </h4>
                <div className="grid gap-4 sm:grid-cols-3">
                  {advNum('hvac_cooling_cop', 'Cooling COP', 'proto default')}
                  {advNum('hvac_heating_cop', 'Heating COP', '3.0')}
                  {advNum('hvac_fan_kw_per_cfm', 'Fan power (kW/CFM)', '0.0005', '0.0001')}
                  <div>
                    <Label>System type</Label>
                    <Select value={adv.hvac_system_type ?? ''} onChange={setAdvField('hvac_system_type')}>
                      <option value="">(default)</option>
                      <option value="packaged_dx">Packaged DX / RTU</option>
                      <option value="heat_pump">Heat pump</option>
                      <option value="chiller">Chiller + AHU</option>
                      <option value="vrf">VRF</option>
                    </Select>
                  </div>
                </div>
              </div>
              <div>
                <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-ink/50">
                  Walls &amp; roof
                </h4>
                <div className="grid gap-4 sm:grid-cols-3">
                  {advNum('wall_area_sf', 'Wall area (sf)', 'derived')}
                  {advNum('wall_u_factor', 'Wall U (BTU/h·ft²·F)', 'code default')}
                  {advNum('wall_absorptance', 'Wall solar absorptance', '0.60')}
                  <div>
                    <Label>Roof type</Label>
                    <Select value={adv.roof_type ?? ''} onChange={setAdvField('roof_type')}>
                      <option value="">(default)</option>
                      <option value="membrane">Membrane (dark)</option>
                      <option value="cool_roof">Cool roof (white)</option>
                      <option value="metal">Metal</option>
                      <option value="built_up">Built-up</option>
                      <option value="shingle">Shingle</option>
                    </Select>
                  </div>
                  {advNum('roof_area_sf', 'Roof area (sf)', 'footprint')}
                  {advNum('roof_u_factor', 'Roof U (BTU/h·ft²·F)', 'code default')}
                  {advNum('roof_absorptance', 'Roof solar absorptance', '0.70')}
                </div>
              </div>
              <div>
                <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-ink/50">
                  Operations &amp; geometry
                </h4>
                <div className="grid gap-4 sm:grid-cols-3">
                  {advNum('operating_hours_per_week', 'Operating hours / week', 'proto default')}
                  {advNum('num_floors', '# floors', 'proto default')}
                  {advNum('floor_to_floor_ft', 'Floor-to-floor (ft)', '13')}
                </div>
              </div>
            </div>
          )}
        </Card>

        {submitError && <ErrorBox message={submitError} />}

        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? 'Creating…' : 'Create Project'}
          </Button>
        </div>
      </form>
    </div>
  );
}

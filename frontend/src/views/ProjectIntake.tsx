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
  const [zipLoading, setZipLoading] = useState(false);
  const [zipError, setZipError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

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

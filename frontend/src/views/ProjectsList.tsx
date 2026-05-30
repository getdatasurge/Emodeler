import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { ProjectSummary } from '../types';
import { Button, ErrorBox, Label, Select, Spinner, TextInput } from '../components/ui';

// IWFA survey workbooks frequently cover a portfolio (Millstone + New Brunswick
// + Evesham in one file). The portfolio importer splits per Building ID and
// creates one project per building, applying the template fields to all.
function PortfolioImportModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (projects: { id: string; name: string; faces_imported: number }[]) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [zip, setZip] = useState('');
  const [buildingType, setBuildingType] = useState('MediumOffice');
  const [area, setArea] = useState('');
  const [namePrefix, setNamePrefix] = useState('');
  const [units, setUnits] = useState<'in' | 'ft'>('in');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setError(null);
    if (!file) { setError('Pick a .xlsx survey workbook.'); return; }
    if (!zip || !buildingType || !area) {
      setError('ZIP, building type, and floor area per project are required.');
      return;
    }
    setBusy(true);
    try {
      const res = await api.importSurveyPortfolio(file, {
        zip,
        building_type: buildingType,
        gross_floor_area_sf: Number(area),
        name_prefix: namePrefix || undefined,
        units,
      });
      onCreated(res.projects);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-3 flex items-start justify-between">
          <h2 className="text-lg font-semibold text-ink">Import portfolio survey</h2>
          <button onClick={onClose} className="text-ink/40 hover:text-ink" aria-label="Close">×</button>
        </div>
        <p className="mb-4 text-xs text-ink/60">
          Reads the IWFA workbook and creates one project per Building ID.
          The template below applies to every project (tune individual ones
          after import).
        </p>
        <div className="space-y-3">
          <div>
            <Label>Survey workbook (.xlsx)</Label>
            <input
              type="file"
              accept=".xlsx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-amber file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-amber-dark"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>ZIP</Label>
              <TextInput value={zip} onChange={(e) => setZip(e.target.value)} placeholder="33540" />
            </div>
            <div>
              <Label>Floor area per project (sf)</Label>
              <TextInput value={area} onChange={(e) => setArea(e.target.value)} type="number" placeholder="20000" />
            </div>
            <div>
              <Label>Building type</Label>
              <Select value={buildingType} onChange={(e) => setBuildingType(e.target.value)}>
                {['SmallOffice', 'MediumOffice', 'LargeOffice', 'PrimarySchool',
                  'SecondarySchool', 'RetailStandalone', 'StripMall', 'Warehouse',
                  'Hospital', 'OutpatientHealthcare', 'Hotel', 'FullServiceRestaurant'].map(
                    (t) => <option key={t} value={t}>{t}</option>
                  )}
              </Select>
            </div>
            <div>
              <Label>Dimension units</Label>
              <Select value={units} onChange={(e) => setUnits(e.target.value as 'in' | 'ft')}>
                <option value="in">Inches (default)</option>
                <option value="ft">Feet</option>
              </Select>
            </div>
            <div className="col-span-2">
              <Label>Project name prefix (optional)</Label>
              <TextInput value={namePrefix} onChange={(e) => setNamePrefix(e.target.value)} placeholder='e.g. "Evesham · "' />
            </div>
          </div>
          {error && <ErrorBox message={error} />}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={busy}>
            {busy ? 'Importing…' : 'Create projects'}
          </Button>
        </div>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: 'bg-green-100 text-green-800',
    in_analysis: 'bg-amber/20 text-amber-dark',
    draft: 'bg-ink/10 text-ink/70',
  };
  return (
    <span
      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${map[status] ?? 'bg-ink/10 text-ink/70'}`}
    >
      {status.replace('_', ' ')}
    </span>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded bg-neutralbg px-2 py-0.5 text-xs text-ink/60">
      {children}
    </span>
  );
}

export function ProjectsList({
  onOpen,
  onNew,
}: {
  onOpen: (id: string) => void;
  onNew: () => void;
}) {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showPortfolio, setShowPortfolio] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const refreshAbortRef = useRef(0);

  function refresh() {
    const token = ++refreshAbortRef.current;
    api
      .listProjects()
      .then((p) => { if (token === refreshAbortRef.current) setProjects(p); })
      .catch((e) => { if (token === refreshAbortRef.current) setError(e.message); });
  }

  useEffect(() => { refresh(); }, []);

  const count = projects?.length ?? 0;

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">Projects</h1>
          <p className="mt-1 max-w-xl text-sm text-ink/60">
            Model window-film energy savings — compare Good / Better / Best films
            with payback, peak-demand cut, and CO₂ avoided for each building.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => setShowPortfolio(true)}>
            Import portfolio (.xlsx)
          </Button>
          <Button onClick={onNew}>+ New Project</Button>
        </div>
      </div>

      {showPortfolio && (
        <PortfolioImportModal
          onClose={() => setShowPortfolio(false)}
          onCreated={(created) => {
            setShowPortfolio(false);
            setImportMsg(
              `Created ${created.length} project${created.length === 1 ? '' : 's'}: ` +
              created.map((p) => p.name).slice(0, 5).join(', ') +
              (created.length > 5 ? `, +${created.length - 5} more` : ''),
            );
            refresh();
          }}
        />
      )}
      {importMsg && (
        <div className="mb-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">
          {importMsg}
        </div>
      )}

      {error && <ErrorBox message={error} />}
      {!projects && !error && <Spinner label="Loading projects…" />}

      {projects && count === 0 && (
        <div className="rounded-xl border-2 border-dashed border-ink/15 bg-white/50 px-6 py-16 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber/15 text-2xl text-amber-dark">
            +
          </div>
          <h2 className="text-lg font-semibold text-ink">No projects yet</h2>
          <p className="mx-auto mt-1 max-w-md text-sm text-ink/60">
            Create your first model: enter a building and ZIP, pick the glazing and
            up to three candidate films, and run the analysis.
          </p>
          <div className="mt-5">
            <Button onClick={onNew}>+ New Project</Button>
          </div>
        </div>
      )}

      {projects && count > 0 && (
        <>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink/40">
            {count} {count === 1 ? 'project' : 'projects'}
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <button
                key={p.id}
                onClick={() => onOpen(p.id)}
                className="group rounded-lg border border-ink/10 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-amber hover:shadow-md"
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-ink">{p.name}</h3>
                  <StatusPill status={p.status} />
                </div>
                <p className="text-sm text-ink/70">{p.customer_name ?? 'No customer'}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Chip>{p.building_type}</Chip>
                  <Chip>ZIP {p.zip}</Chip>
                  {p.climate_zone && <Chip>CZ {p.climate_zone}</Chip>}
                </div>
                <div className="mt-4 text-sm font-semibold text-amber opacity-0 transition group-hover:opacity-100">
                  Open →
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

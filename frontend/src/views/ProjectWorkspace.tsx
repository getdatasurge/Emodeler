import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type {
  BaseGlazing,
  Comparison,
  Film,
  Job,
  Project,
} from '../types';
import { Button, Card, ErrorBox, Label, SectionTitle, Select, Spinner, TextInput } from '../components/ui';
import { GlazingFaces } from '../components/GlazingFaces';
import { FilmCandidates } from '../components/FilmCandidates';
import type { CandidateDraft } from '../components/FilmCandidates';
import { ResultsDashboard } from '../components/ResultsDashboard';

type RunState =
  | { phase: 'idle' }
  | { phase: 'running'; completed: number; total: number }
  | { phase: 'failed'; message: string }
  | { phase: 'completed' };

const POLL_MS = 2000;

export function ProjectWorkspace({
  projectId,
  onBack,
}: {
  projectId: string;
  onBack: () => void;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [films, setFilms] = useState<Film[]>([]);
  const [baseGlazings, setBaseGlazings] = useState<BaseGlazing[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [candidates, setCandidates] = useState<CandidateDraft[]>([
    { label: '', film_sku: '', installed_cost_usd: '' },
  ]);
  const [run, setRun] = useState<RunState>({ phase: 'idle' });
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<{ comparison: Comparison; jobId: string } | null>(null);
  const [demandCharge, setDemandCharge] = useState('');
  const [scalingBasis, setScalingBasis] = useState<'floor' | 'glazing'>('floor');
  const pollRef = useRef<number | null>(null);

  // Initial load of project + catalogs.
  useEffect(() => {
    let active = true;
    Promise.all([
      api.getProject(projectId),
      api.listFilms(),
      api.listBaseGlazings(),
    ])
      .then(([p, f, g]) => {
        if (!active) return;
        setProject(p);
        setFilms(f);
        setBaseGlazings(g);
        // Pre-fill candidates from any stored scenarios.
        if (p.scenarios.length > 0) {
          setCandidates(
            p.scenarios.slice(0, 3).map((s) => ({
              label: s.label,
              film_sku: s.film_sku,
              installed_cost_usd: String(s.installed_cost_usd),
            })),
          );
        }
        // Show the latest completed analysis immediately (no re-run needed).
        if (p.status === 'completed') {
          api
            .projectResults(p.id)
            .then((r) => active && setResult({ comparison: r.comparison, jobId: r.job_id }))
            .catch(() => {});
        }
      })
      .catch((e) => active && setLoadError((e as Error).message));
    return () => {
      active = false;
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [projectId]);

  function applyJob(job: Job) {
    if (job.status === 'completed') {
      if (pollRef.current) window.clearInterval(pollRef.current);
      setRun({ phase: 'completed' });
      api
        .jobResults(job.job_id)
        .then((comparison) => setResult({ comparison, jobId: job.job_id }))
        .catch((e) => setRun({ phase: 'failed', message: (e as Error).message }));
    } else if (job.status === 'failed') {
      if (pollRef.current) window.clearInterval(pollRef.current);
      setRun({
        phase: 'failed',
        message: job.error_message || 'Analysis failed.',
      });
    } else {
      setRun({
        phase: 'running',
        completed: job.progress?.scenarios_completed ?? 0,
        total: job.progress?.scenarios_total ?? candidates.length,
      });
    }
  }

  function startPolling(jobId: string) {
    pollRef.current = window.setInterval(async () => {
      try {
        const job = await api.getJob(jobId);
        applyJob(job);
      } catch (e) {
        if (pollRef.current) window.clearInterval(pollRef.current);
        setRun({ phase: 'failed', message: (e as Error).message });
      }
    }, POLL_MS);
  }

  async function handleRun() {
    if (!project) return;
    setRunError(null);

    const ready = candidates.filter(
      (c) => c.film_sku && c.label && c.installed_cost_usd !== '',
    );
    if (project.faces.length === 0) {
      setRunError('Add at least one glazing face before running.');
      return;
    }
    if (ready.length === 0) {
      setRunError(
        'Add at least one film candidate with a label, SKU, and installed cost.',
      );
      return;
    }

    setRun({ phase: 'running', completed: 0, total: ready.length });
    setResult(null);
    try {
      const resp = await api.runCalc({
        project_id: project.id,
        scenarios: ready.map((c) => ({
          label: c.label,
          film_sku: c.film_sku,
          installed_cost_usd: Number(c.installed_cost_usd),
        })),
        options: {
          film_life_yrs: 15,
          discount_rate: 0.05,
          utility_escalation: 0.025,
          include_demand_charge: Number(demandCharge) > 0,
          demand_charge_usd_per_kw: Number(demandCharge) || 0,
          scaling_basis: scalingBasis,
        },
      });
      startPolling(resp.job_id);
    } catch (e) {
      setRun({ phase: 'idle' });
      setRunError((e as Error).message);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-8">
        <BackLink onBack={onBack} />
        <ErrorBox message={loadError} />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-8">
        <Spinner label="Loading project…" />
      </div>
    );
  }

  const firstFaceGlazing = project.faces[0]?.base_glazing_id ?? null;
  const isRunning = run.phase === 'running';

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <BackLink onBack={onBack} />

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ink">{project.name}</h1>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink/60">
          {project.customer_name && <span>{project.customer_name}</span>}
          <span>{project.building_type}</span>
          <span>
            {project.gross_floor_area_sf.toLocaleString()} sf
          </span>
          {project.climate_zone && <span>CZ {project.climate_zone}</span>}
          <span>ZIP {project.zip}</span>
          {project.utility_rate_usd_kwh != null && (
            <span>${project.utility_rate_usd_kwh}/kWh</span>
          )}
          {project.egrid_subregion && (
            <span>eGRID {project.egrid_subregion}</span>
          )}
        </div>
      </div>

      <div className="space-y-6">
        <Card>
          <SectionTitle step={1}>Glazing faces</SectionTitle>
          <GlazingFaces
            project={project}
            baseGlazings={baseGlazings}
            onProjectUpdate={setProject}
          />
        </Card>

        <Card>
          <SectionTitle step={2}>Film candidates (1–3)</SectionTitle>
          <FilmCandidates
            films={films}
            baseGlazingId={firstFaceGlazing}
            candidates={candidates}
            onChange={setCandidates}
          />
        </Card>

        <Card>
          <SectionTitle step={3}>Run analysis</SectionTitle>
          {runError && (
            <div className="mb-3">
              <ErrorBox message={runError} />
            </div>
          )}
          {run.phase === 'failed' && (
            <div className="mb-3">
              <ErrorBox message={`Analysis failed: ${run.message}`} />
            </div>
          )}
          <div className="mb-4 grid max-w-xl gap-4 sm:grid-cols-2">
            <div>
              <Label>Utility demand charge ($/kW·mo, optional)</Label>
              <TextInput
                type="number"
                step="0.01"
                value={demandCharge}
                onChange={(e) => setDemandCharge(e.target.value)}
                placeholder="e.g. 15.00 — adds demand savings to the result"
              />
            </div>
            <div>
              <Label>Scale prototype by</Label>
              <Select
                value={scalingBasis}
                onChange={(e) => setScalingBasis(e.target.value as 'floor' | 'glazing')}
              >
                <option value="floor">Floor area (EFILM convention, default)</option>
                <option value="glazing">Glazing area (more physical for film)</option>
              </Select>
              <p className="mt-1 text-xs text-ink/50">
                The audit bundle stamps both factors regardless of which is applied.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Button onClick={handleRun} disabled={isRunning}>
              {isRunning ? 'Running…' : 'Run Analysis'}
            </Button>
            {isRunning && (
              <Spinner
                label={`Simulating scenarios ${run.completed}/${run.total}…`}
              />
            )}
          </div>
        </Card>

        {run.phase === 'completed' && !result && (
          <div className="pt-2">
            <Spinner label="Loading results…" />
          </div>
        )}
        {result && (
          <div className="pt-2">
            <ResultsDashboard comparison={result.comparison} jobId={result.jobId} />
          </div>
        )}
      </div>
    </div>
  );
}

function BackLink({ onBack }: { onBack: () => void }) {
  return (
    <button
      onClick={onBack}
      className="mb-4 text-sm text-ink/60 hover:text-ink"
    >
      &larr; Back to projects
    </button>
  );
}

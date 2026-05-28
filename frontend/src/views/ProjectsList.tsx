import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ProjectSummary } from '../types';
import { Button, ErrorBox, Spinner } from '../components/ui';

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

  useEffect(() => {
    let active = true;
    api
      .listProjects()
      .then((p) => active && setProjects(p))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, []);

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
        <Button onClick={onNew}>+ New Project</Button>
      </div>

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

import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ProjectSummary } from '../types';
import { Button, Card, ErrorBox, Spinner } from '../components/ui';

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

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Projects</h1>
          <p className="text-sm text-ink/60">
            Select a project to model window-film savings, or start a new one.
          </p>
        </div>
        <Button onClick={onNew}>+ New Project</Button>
      </div>

      {error && <ErrorBox message={error} />}
      {!projects && !error && <Spinner label="Loading projects…" />}

      {projects && projects.length === 0 && (
        <Card>
          <p className="text-ink/70">
            No projects yet. Click "New Project" to create your first model.
          </p>
        </Card>
      )}

      {projects && projects.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => onOpen(p.id)}
              className="text-left"
            >
              <Card className="h-full transition hover:border-amber hover:shadow-md">
                <div className="mb-2 flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-ink">{p.name}</h3>
                  <StatusPill status={p.status} />
                </div>
                <p className="text-sm text-ink/70">
                  {p.customer_name ?? 'No customer'}
                </p>
                <div className="mt-3 flex gap-4 text-xs text-ink/60">
                  <span>{p.building_type}</span>
                  <span>ZIP {p.zip}</span>
                  {p.climate_zone && <span>CZ {p.climate_zone}</span>}
                </div>
              </Card>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

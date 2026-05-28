import { useEffect, useState } from 'react';
import { api } from './api';
import type { Meta } from './types';
import { Header } from './components/Header';
import { EstimateBanner } from './components/EstimateBanner';
import { ProjectsList } from './views/ProjectsList';
import { ProjectIntake } from './views/ProjectIntake';
import { ProjectWorkspace } from './views/ProjectWorkspace';

type Route =
  | { view: 'list' }
  | { view: 'intake' }
  | { view: 'workspace'; projectId: string };

export default function App() {
  const [route, setRoute] = useState<Route>({ view: 'list' });
  const [meta, setMeta] = useState<Meta | null>(null);

  // Global estimate banner data.
  useEffect(() => {
    api
      .meta()
      .then(setMeta)
      .catch(() => setMeta(null));
  }, []);

  const showBanner =
    meta && !meta.energyplus_available && meta.notice;

  return (
    <div className="min-h-full bg-neutralbg text-ink">
      <Header onHome={() => setRoute({ view: 'list' })} />
      {showBanner && <EstimateBanner notice={meta!.notice!} />}

      {route.view === 'list' && (
        <ProjectsList
          onOpen={(id) => setRoute({ view: 'workspace', projectId: id })}
          onNew={() => setRoute({ view: 'intake' })}
        />
      )}

      {route.view === 'intake' && (
        <ProjectIntake
          onCreated={(p) =>
            setRoute({ view: 'workspace', projectId: p.id })
          }
          onCancel={() => setRoute({ view: 'list' })}
        />
      )}

      {route.view === 'workspace' && (
        <ProjectWorkspace
          projectId={route.projectId}
          onBack={() => setRoute({ view: 'list' })}
        />
      )}
    </div>
  );
}

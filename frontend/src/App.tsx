import { useEffect, useState } from 'react';
import { api, ApiError } from './api';
import type { Meta } from './types';
import { Header } from './components/Header';
import { EstimateBanner } from './components/EstimateBanner';
import { Spinner } from './components/ui';
import { ToastStack } from './components/Toast';
import { useSession, signOut } from './auth/useSession';
import { Login } from './auth/Login';
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
  const [apiDown, setApiDown] = useState(false);

  // Global estimate banner data. A network error means the backend API is not
  // reachable (e.g. a static deploy with no backend configured).
  useEffect(() => {
    api
      .meta()
      .then((m) => {
        setMeta(m);
        setApiDown(false);
      })
      .catch((e) => {
        setMeta(null);
        setApiDown(e instanceof ApiError && e.status === 0);
      });
  }, []);

  const showBanner = meta && !meta.energyplus_available && meta.notice;

  // Auth gate — inert (always "signed in") when Supabase env is unset.
  const { session, loading: authLoading, enabled: authEnabled } = useSession();
  if (authEnabled && authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutralbg">
        <Spinner label="Loading…" />
      </div>
    );
  }
  if (authEnabled && !session) {
    return <Login />;
  }

  return (
    <div className="min-h-full bg-neutralbg text-ink">
      <ToastStack />
      <Header
        onHome={() => setRoute({ view: 'list' })}
        onSignOut={authEnabled ? () => void signOut() : undefined}
      />
      {apiDown && (
        <EstimateBanner
          notice="Static preview — the EnergyModeler backend API is not reachable from this site, so live data and analyses are unavailable. Deploy the backend and rebuild with VITE_API_BASE set to its URL to enable the full workflow."
        />
      )}
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

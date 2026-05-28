import { useEffect, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { authEnabled, supabase } from './supabase';

export interface SessionState {
  session: Session | null;
  loading: boolean;
  enabled: boolean;
}

// When auth is disabled (no Supabase env) the app runs as the single-tenant
// beta: no login, no loading gate.
export function useSession(): SessionState {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(authEnabled);

  useEffect(() => {
    if (!authEnabled || !supabase) return;
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) =>
      setSession(s),
    );
    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  return { session, loading, enabled: authEnabled };
}

export async function signOut(): Promise<void> {
  if (supabase) await supabase.auth.signOut();
}

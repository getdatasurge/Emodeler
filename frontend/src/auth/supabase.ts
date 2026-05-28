// Supabase client — only instantiated when both env vars are present, so the
// single-tenant beta (no Supabase project yet) runs untouched.
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const authEnabled = Boolean(url && anonKey);
export const supabase: SupabaseClient | null = authEnabled
  ? createClient(url as string, anonKey as string)
  : null;

// Cached access token so the API client can attach it synchronously per request.
let accessToken: string | null = null;
if (supabase) {
  supabase.auth.getSession().then(({ data }) => {
    accessToken = data.session?.access_token ?? null;
  });
  supabase.auth.onAuthStateChange((_event, session) => {
    accessToken = session?.access_token ?? null;
  });
}

export const getAccessToken = (): string | null => accessToken;

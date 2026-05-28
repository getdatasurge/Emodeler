/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Absolute base URL of a deployed EnergyModeler backend, e.g.
   *  "https://api.example.com". Empty -> same-origin /api (dev proxy). */
  readonly VITE_API_BASE?: string;
  /** Supabase project URL + anon key. When both are set, the app requires
   *  login; when unset, it runs as the no-auth single-tenant beta. */
  readonly VITE_SUPABASE_URL?: string;
  readonly VITE_SUPABASE_ANON_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

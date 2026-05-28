/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Absolute base URL of a deployed EnergyModeler backend, e.g.
   *  "https://api.example.com". Empty -> same-origin /api (dev proxy). */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

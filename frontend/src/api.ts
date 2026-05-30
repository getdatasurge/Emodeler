// Typed fetch wrapper + endpoint helpers. Uses plain fetch; /api is proxied to
// the backend by Vite (dev) or served same-origin (prod).
import { getAccessToken } from './auth/supabase';
import type {
  BaseGlazing,
  CalcRunRequest,
  CalcRunResponse,
  ClimateZone,
  Comparison,
  Egrid,
  FaceInput,
  Film,
  Job,
  Meta,
  Pairing,
  Project,
  ProjectCreate,
  ProjectSummary,
  Utility,
} from './types';

// API origin. Empty (the default) keeps requests same-origin (`/api/...`) so the
// Vite dev proxy / a co-hosted backend works. For a static deploy (e.g. GitHub
// Pages) set VITE_API_BASE at build time to a deployed backend URL.
const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');
export const apiBaseConfigured = API_BASE.length > 0;

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  const token = getAccessToken();
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers as Record<string, string> | undefined),
      },
    });
  } catch (e) {
    throw new ApiError(
      `Network error contacting ${path}. Is the backend running?`,
      0,
      e,
    );
  }

  const text = await resp.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!resp.ok) {
    const detail = extractError(data);
    throw new ApiError(detail || `Request failed (${resp.status})`, resp.status, data);
  }
  return data as T;
}

function extractError(body: unknown): string | null {
  if (body && typeof body === 'object') {
    // New standard envelope: {error, code, request_id, details?}.
    if ('error' in body && typeof (body as { error: unknown }).error === 'string') {
      return (body as { error: string }).error;
    }
    // Legacy FastAPI shape: {detail: "..."} or {detail: {error: "..."}}.
    if ('detail' in body) {
      const d = (body as { detail: unknown }).detail;
      if (typeof d === 'string') return d;
      if (d && typeof d === 'object' && 'error' in d) {
        return String((d as { error: unknown }).error);
      }
    }
  }
  return null;
}

export const api = {
  meta: () => request<Meta>('/api/meta'),

  listProjects: () => request<ProjectSummary[]>('/api/projects'),
  getProject: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (body: ProjectCreate) =>
    request<Project>('/api/projects', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  addFace: (projectId: string, body: FaceInput) =>
    request<Project>(`/api/projects/${projectId}/faces`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  importSurvey: async (
    projectId: string,
    file: File,
    mode: 'replace' | 'append' = 'replace',
  ) => {
    // Multipart upload — can't go through request() which sets a JSON
    // Content-Type. Hand-roll fetch with the same auth + error envelope.
    const form = new FormData();
    form.append('file', file);
    const token = getAccessToken();
    const resp = await fetch(
      `${API_BASE}/api/projects/${projectId}/import-survey-xlsx?mode=${mode}`,
      {
        method: 'POST',
        body: form,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      },
    );
    const text = await resp.text();
    let data: unknown = null;
    if (text) {
      try { data = JSON.parse(text); } catch { data = text; }
    }
    if (!resp.ok) {
      throw new ApiError(
        extractError(data) || `Survey import failed (${resp.status})`,
        resp.status,
        data,
      );
    }
    return data as {
      imported: number;
      mode: string;
      units: string;
      project: Project;
    };
  },

  importSurveyPortfolio: async (
    file: File,
    template: {
      zip: string;
      building_type: string;
      gross_floor_area_sf: number;
      climate_zone?: string | null;
      name_prefix?: string;
      units?: 'in' | 'ft';
    },
  ) => {
    const params = new URLSearchParams({
      zip: template.zip,
      building_type: template.building_type,
      gross_floor_area_sf: String(template.gross_floor_area_sf),
      units: template.units ?? 'in',
    });
    if (template.climate_zone) params.set('climate_zone', template.climate_zone);
    if (template.name_prefix) params.set('name_prefix', template.name_prefix);

    const form = new FormData();
    form.append('file', file);
    const token = getAccessToken();
    const resp = await fetch(
      `${API_BASE}/api/projects/import-survey-portfolio?${params.toString()}`,
      {
        method: 'POST',
        body: form,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      },
    );
    const text = await resp.text();
    let data: unknown = null;
    if (text) {
      try { data = JSON.parse(text); } catch { data = text; }
    }
    if (!resp.ok) {
      throw new ApiError(
        extractError(data) || `Portfolio import failed (${resp.status})`,
        resp.status,
        data,
      );
    }
    return data as {
      created: number;
      units: string;
      projects: { id: string; name: string; faces_imported: number }[];
    };
  },

  climateZone: (zip: string) => request<ClimateZone>(`/api/climate-zone/${zip}`),
  egrid: (zip: string) => request<Egrid>(`/api/egrid/${zip}`),
  utility: (zip: string) => request<Utility>(`/api/utility/${zip}`),

  listFilms: () => request<Film[]>('/api/films'),
  listBaseGlazings: () => request<BaseGlazing[]>('/api/base-glazings'),
  pairing: (sku: string, baseGlazingId: string) =>
    request<Pairing>(`/api/films/${encodeURIComponent(sku)}/pairings/${baseGlazingId}`),

  runCalc: (body: CalcRunRequest) =>
    request<CalcRunResponse>('/api/calc/run', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getJob: (jobId: string) => request<Job>(`/api/jobs/${jobId}`),
  jobResults: (jobId: string) => request<Comparison>(`/api/jobs/${jobId}/results`),
  projectResults: (projectId: string) =>
    request<{ job_id: string; engine_mode: string; comparison: Comparison }>(
      `/api/projects/${projectId}/results`,
    ),
};

// Absolute-ish URLs for links the browser opens directly (reports / downloads).
export const reportUrl = (jobId: string) => `${API_BASE}/api/reports/${jobId}`;
export const reportPdfUrl = (jobId: string) => `${API_BASE}/api/reports/${jobId}/pdf`;
export const auditBundleUrl = (jobId: string) => `${API_BASE}/api/jobs/${jobId}/audit-bundle`;

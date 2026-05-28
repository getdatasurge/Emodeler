// Typed fetch wrapper + endpoint helpers. Uses plain fetch; /api is proxied to
// the backend by Vite (dev) or served same-origin (prod).
import type {
  BaseGlazing,
  CalcRunRequest,
  CalcRunResponse,
  ClimateZone,
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
  try {
    resp = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
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
  if (body && typeof body === 'object' && 'detail' in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === 'string') return d;
    if (d && typeof d === 'object' && 'error' in d) {
      return String((d as { error: unknown }).error);
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
};

// Absolute-ish URLs for links the browser opens directly (reports / downloads).
export const reportUrl = (jobId: string) => `/api/reports/${jobId}`;
export const auditBundleUrl = (jobId: string) => `/api/jobs/${jobId}/audit-bundle`;

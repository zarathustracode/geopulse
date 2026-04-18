import type { Defect, DefectFilters, DefectStatus } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${path} failed: ${response.status}`);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function buildQuery(filters: DefectFilters): string {
  const params = new URLSearchParams();
  if (filters.type) params.set('type', filters.type);
  if (filters.status) params.set('status', filters.status);
  if (filters.minConfidence !== undefined) {
    params.set('minConfidence', filters.minConfidence.toString());
  }
  if (filters.bbox) {
    params.set('minLongitude', filters.bbox.minLongitude.toString());
    params.set('minLatitude', filters.bbox.minLatitude.toString());
    params.set('maxLongitude', filters.bbox.maxLongitude.toString());
    params.set('maxLatitude', filters.bbox.maxLatitude.toString());
  }
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export const defectsApi = {
  list: (filters: DefectFilters = {}) =>
    request<Defect[]>(`/defects${buildQuery(filters)}`),

  get: (id: string) => request<Defect>(`/defects/${id}`),

  updateStatus: (id: string, status: DefectStatus) =>
    request<Defect>(`/defects/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
};

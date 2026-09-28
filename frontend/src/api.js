// Thin wrapper around fetch for the Finance Tracker API.
// The base URL comes from VITE_API_URL; empty means "same origin" (the vite
// dev server proxies /api to the backend).
const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : `Request failed (${status})`);
    this.status = status;
  }
}

function detailOf(data) {
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data?.detail)) {
    // FastAPI validation errors: surface the first human-readable message.
    const first = data.detail[0];
    return first?.msg ? `${first.loc?.join('.')}: ${first.msg}` : 'Invalid request';
  }
  return 'Request failed';
}

export async function api(path, { method = 'GET', body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, detailOf(data));
  return data;
}

/** POST multipart/form-data (used by the CSV import endpoint). */
export async function apiUpload(path, formData, token) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, detailOf(data));
  return data;
}

export const money = (n) =>
  (n < 0 ? '-' : '') +
  '$' +
  Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const todayMonth = () => new Date().toISOString().slice(0, 7);
export const todayDate = () => new Date().toISOString().slice(0, 10);

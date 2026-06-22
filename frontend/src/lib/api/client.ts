/**
 * Type-safe API client for Alejandría backend.
 */

import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import { user, setUser, clearUser } from '$stores/auth';
import { get } from 'svelte/store';
import type * as Types from './types';

const API_BASE = '';

export class APIError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: any,
  options: { isForm?: boolean; responseType?: 'json' | 'blob' | 'text' } = {}
): Promise<T> {
  const headers: Record<string, string> = {};

  if (!options.isForm) {
    headers['Content-Type'] = 'application/json';
  }

  // Attach CSRF token for non-GET requests
  if (browser && method !== 'GET' && method !== 'HEAD') {
    const csrf = getCookie('alejandria_csrf');
    if (csrf) {
      headers['X-CSRF-Token'] = csrf;
    }
  }

  const res = await fetch(API_BASE + path, {
    method,
    headers,
    credentials: 'include',
    body: body !== undefined ? (options.isForm ? body : JSON.stringify(body)) : undefined,
  });

  if (res.status === 401) {
    if (browser) {
      clearUser();
      // Don't redirect if already on login page
      if (!window.location.pathname.startsWith('/login')) {
        goto('/login?next=' + encodeURIComponent(window.location.pathname));
      }
    }
    throw new APIError(401, 'Not authenticated');
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {}
    throw new APIError(res.status, detail);
  }

  if (res.status === 204 || options.responseType === 'blob' || options.responseType === 'text') {
    return res as unknown as T;
  }

  return res.json();
}

function getCookie(name: string): string | null {
  if (!browser) return null;
  const m = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[2]) : null;
}

const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: any) => request<T>('POST', path, body),
  put: <T>(path: string, body?: any) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: any) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
  postForm: <T>(path: string, form: FormData) =>
    request<T>('POST', path, form, { isForm: true }),
  putForm: <T>(path: string, form: FormData) =>
    request<T>('PUT', path, form, { isForm: true }),
  getBlob: (path: string) => request<Blob>('GET', path, undefined, { responseType: 'blob' }),
};

// --- Auth ---
export const auth = {
  login: (username: string, password: string) =>
    api.post<Types.TokenResponse>('/api/auth/login/json', { username, password }),
  logout: () => api.post<{ status: string }>('/api/auth/logout'),
  me: () => api.get<Types.User>('/api/auth/me'),
  updateMe: (data: Partial<Types.User>) => api.patch<Types.User>('/api/auth/me', data),
  appInfo: () => api.get<{ version: string; oidc_enabled: boolean; smtp_configured: boolean }>(
    '/api/settings/app'
  ),
};

// --- Library ---
export const library = {
  stats: () => api.get<Types.LibraryStats>('/api/library/stats'),
  authors: () => api.get<Types.BookAuthor[]>('/api/library/authors'),
  author: (id: number) => api.get<{ id: number; name: string; books: Types.BookSummary[] }>(`/api/library/authors/${id}`),
  tags: () => api.get<Types.TagInfo[]>('/api/library/tags'),
  tag: (id: number) => api.get<{ id: number; name: string; books: Types.BookSummary[] }>(`/api/library/tags/${id}`),
  series: () => api.get<Types.SeriesInfo[]>('/api/library/series'),
  seriesBooks: (id: number) => api.get<{ id: number; name: string; books: Types.BookSummary[] }>(`/api/library/series/${id}`),
  rescan: () => api.post<{ status: string }>('/api/library/rescan'),
  rescanStatus: () => api.get<{ is_scanning: boolean; last_scan: string | null }>('/api/library/rescan/status'),
};

// --- Books ---
export const books = {
  list: (params: {
    page?: number;
    page_size?: number;
    search?: string;
    author?: number;
    tag?: number;
    series?: number;
    sort?: string;
    order?: 'asc' | 'desc';
  } = {}) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
    }
    return api.get<Types.BookListResponse>(`/api/books?${q.toString()}`);
  },
  get: (id: number) => api.get<Types.BookDetail>(`/api/books/${id}`),
  formats: (id: number) => api.get<{ book_id: number; formats: { fmt: string; size: number }[] }>(`/api/books/${id}/formats`),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.postForm<{ status: string; message: string }>('/api/books/upload', formData);
  },
  update: (id: number, formData: FormData) =>
    api.putForm<Types.BookDetail>(`/api/books/${id}`, formData),
  delete: (id: number) => api.delete<void>(`/api/books/${id}`),
};

// --- Reader ---
export const reader = {
  file: (bookId: number, fmt?: string) =>
    `/api/reader/${bookId}/file${fmt ? `?fmt=${fmt}` : ''}`,
  download: (bookId: number, fmt?: string) =>
    `/api/reader/${bookId}/download${fmt ? `?fmt=${fmt}` : ''}`,
  progress: (bookId: number) => api.get<Types.ProgressRead | null>(`/api/reader/${bookId}/progress`),
  updateProgress: (data: Types.ProgressUpdate) =>
    api.put<Types.ProgressRead>(`/api/reader/${data.book_id}/progress`, data),
  deleteProgress: (bookId: number) =>
    api.delete<{ status: string }>(`/api/reader/${bookId}/progress`),
};

// --- Highlights ---
export const highlights = {
  list: (bookId?: number) =>
    api.get<Types.Highlight[]>(`/api/highlights${bookId ? `?book_id=${bookId}` : ''}`),
  create: (data: {
    book_id: number;
    cfi: string;
    text: string;
    color?: string;
    style?: string;
    chapter?: string;
    page?: number;
  }) => api.post<Types.Highlight>('/api/highlights', data),
  update: (id: number, data: Partial<Types.Highlight>) =>
    api.patch<Types.Highlight>(`/api/highlights/${id}`, data),
  delete: (id: number) => api.delete<void>(`/api/highlights/${id}`),
  exportMarkdown: (bookId?: number) =>
    `/api/highlights/export?format=markdown${bookId ? `&book_id=${bookId}` : ''}`,
};

// --- Shelves ---
export const shelves = {
  list: () => api.get<Types.Shelf[]>('/api/shelves'),
  create: (data: Partial<Types.Shelf>) => api.post<Types.Shelf>('/api/shelves', data),
  get: (id: number) => api.get<Types.Shelf & { book_ids: number[]; books: Types.BookSummary[] }>(`/api/shelves/${id}`),
  update: (id: number, data: Partial<Types.Shelf>) =>
    api.patch<Types.Shelf>(`/api/shelves/${id}`, data),
  delete: (id: number) => api.delete<void>(`/api/shelves/${id}`),
  addBook: (shelfId: number, bookId: number) =>
    api.post<{ status: string }>(`/api/shelves/${shelfId}/books/${bookId}`),
  removeBook: (shelfId: number, bookId: number) =>
    api.delete<void>(`/api/shelves/${shelfId}/books/${bookId}`),
};

// --- Stats ---
export const stats = {
  overview: () => api.get<{
    total_books_started: number;
    books_finished: number;
    currently_reading: number;
    total_reading_time_seconds: number;
    total_reading_time_hours: number;
    average_finish_pct: number;
  }>('/api/stats/overview'),
  streak: () => api.get<{ current_streak: number; longest_streak: number }>('/api/stats/streak'),
  byYear: () => api.get<Record<string, number>>('/api/stats/by-year'),
  daily: (days = 30) => api.get<{ date: string; minutes: number }[]>(`/api/stats/daily?days=${days}`),
};

// --- Kindle ---
export const kindle = {
  send: (bookId: number, toEmail?: string, targetFormat = 'EPUB') =>
    api.post<{ status: string; to: string; book_id: number; title: string }>(
      '/api/kindle/send',
      { book_id: bookId, to_email: toEmail, target_format: targetFormat }
    ),
  status: () => api.get<{
    smtp_configured: boolean;
    user_kindle_email: string | null;
    default_kindle_emails: string[];
  }>('/api/kindle/status'),
};

// --- Conversion ---
export const conversion = {
  convert: (bookId: number, target: string, source?: string) =>
    api.post<{ status: string }>(`/api/convert/${bookId}/convert?target=${target}${source ? `&source=${source}` : ''}`),
};

// --- User management (admin) ---
export const users = {
  list: () => api.get<Types.User[]>('/api/settings/users'),
  create: (data: {
    username: string;
    email?: string;
    password: string;
    role: Types.UserRole;
    display_name?: string;
  }) => api.post<Types.User>('/api/settings/users', data),
  update: (id: number, data: Partial<Types.User> & { password?: string }) =>
    api.patch<Types.User>(`/api/settings/users/${id}`, data),
  delete: (id: number) => api.delete<void>(`/api/settings/users/${id}`),
};

export default api;

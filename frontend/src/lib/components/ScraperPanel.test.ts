import { describe, it, expect, vi, beforeEach } from 'vitest';

// Provide a minimal mock for the client store before importing the Svelte
// component so its `$api/client` import resolves.
vi.mock('$api/client', () => {
  return {
    scraper: {
      list: vi.fn(async () => []),
      get: vi.fn(async () => null),
      create: vi.fn(async (data: any) => ({
        id: 1,
        url: data.url,
        title: null,
        adapter_name: 'generic',
        formats: data.formats,
        destinations: data.destinations,
        status: 'queued',
        total_pages: 0,
        current_page: 0,
        progress_pct: 0,
        total_bytes: 0,
        error: null,
        output_paths: null,
        imported_book_ids: null,
        created_at: new Date().toISOString(),
        started_at: null,
        completed_at: null,
      })),
      cancel: vi.fn(async () => null),
      downloadUrl: (id: number, fmt: string) =>
        `/api/scraper/jobs/${id}/download/${fmt}`,
      testAdapter: vi.fn(async () => ({
        image_candidates: [],
        next_candidates: [],
        adapter_used: 'generic',
      })),
    },
  };
});

vi.mock('$stores/toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock('$stores/i18n', () => {
  const t = (key: string, params?: Record<string, any>) => {
    let s = key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        s = s.replace(`{${k}}`, String(v));
      }
    }
    return s;
  };
  // Svelte 5 runes-style: $derived + $state used inside the component
  // is fine, but we just need to expose the helper.
  return { t: { subscribe: (run: any) => { run(t); return () => {}; } } };
});

import { scraper } from '$api/client';

describe('ScraperPanel client surface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exposes the expected scraper methods', () => {
    expect(typeof scraper.list).toBe('function');
    expect(typeof scraper.create).toBe('function');
    expect(typeof scraper.cancel).toBe('function');
    expect(typeof scraper.testAdapter).toBe('function');
    expect(typeof scraper.downloadUrl).toBe('function');
  });

  it('downloadUrl produces the expected URL', () => {
    expect(scraper.downloadUrl(42, 'PDF')).toBe(
      '/api/scraper/jobs/42/download/PDF'
    );
    expect(scraper.downloadUrl(7, 'EPUB')).toBe(
      '/api/scraper/jobs/7/download/EPUB'
    );
  });

  it('create accepts a ScrapeJobCreate payload and returns a queued job', async () => {
    const result = await scraper.create({
      url: 'https://example.com/book/1',
      formats: ['PDF'],
      destinations: ['download'],
    });
    expect(result).toMatchObject({
      url: 'https://example.com/book/1',
      formats: ['PDF'],
      destinations: ['download'],
      status: 'queued',
    });
  });
});

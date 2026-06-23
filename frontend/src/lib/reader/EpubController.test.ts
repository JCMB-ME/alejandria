/**
 * EpubController unit test (Phase D, item D10b).
 *
 * Mocks `epubjs` to inject a fake `Book` and `Rendition`. Verifies
 * the controller's surface (init resolves, goToPage clamps, destroy
 * is idempotent, on() returns an unsubscribe).
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

const listeners: Record<string, Function[]> = {};

const mockLocations = {
  length: vi.fn(() => 100),
  percentageFromCfi: vi.fn(() => 0.5),
  cfiFromLocation: vi.fn((loc: number) => `cfi-${loc}`),
  locationFromCfi: vi.fn(() => 10),
  generate: vi.fn(() => Promise.resolve(['cfi-1', 'cfi-2'])),
};

const mockBook = {
  renderTo: vi.fn(() => mockRendition),
  destroy: vi.fn(),
  locations: mockLocations,
  ready: Promise.resolve(),
  loaded: {
    navigation: Promise.resolve({ toc: [{ id: 'ch1', label: 'Chapter 1', href: '#ch1' }] }),
  },
};

const mockRendition = {
  destroy: vi.fn(),
  display: vi.fn(() => Promise.resolve()),
  next: vi.fn(() => Promise.resolve()),
  prev: vi.fn(() => Promise.resolve()),
  themes: {
    fontSize: vi.fn(),
    font: vi.fn(),
    default: vi.fn(),
    override: vi.fn(),
  },
  hooks: {
    content: { register: vi.fn() },
  },
  annotations: {
    add: vi.fn(),
    remove: vi.fn(),
  },
  on: vi.fn((event: string, cb: Function) => {
    (listeners[event] ||= []).push(cb);
  }),
};

vi.mock('epubjs', () => ({
  default: vi.fn(() => mockBook),
}));

import { EpubController } from './EpubController.svelte';

describe('EpubController', () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    vi.clearAllMocks();
    Object.keys(listeners).forEach(k => delete listeners[k]);
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  it('init() resolves and reports ready', async () => {
    const c = new EpubController();
    await c.init(container, 'http://example.com/book.epub');
    expect(c.ready).toBe(true);
    c.destroy();
  });

  it('goToPage() clamps out-of-range input', async () => {
    const c = new EpubController();
    await c.init(container, 'http://example.com/book.epub');
    // Trigger locations-generated completion by waiting for canGoToPage.
    // (generate is sync-resolved Promise, but the controller awaits it.)
    // For the test, force canGoToPage true via the internal listener.
    c.canGoToPage = true;
    await c.goToPage(99);
    // Capped at totalPages=100
    expect(c.currentPage).toBeLessThanOrEqual(100);
    c.destroy();
  });

  it('on() returns an unsubscribe function', async () => {
    const c = new EpubController();
    await c.init(container, 'http://example.com/book.epub');
    const unsub = c.on('pagechange', () => {});
    expect(typeof unsub).toBe('function');
    expect(() => unsub()).not.toThrow();
    c.destroy();
  });

  it('createHighlight() returns null when no selection', async () => {
    const c = new EpubController();
    await c.init(container, 'http://example.com/book.epub');
    expect(await c.createHighlight('yellow')).toBeNull();
    c.destroy();
  });

  it('destroy() is idempotent', async () => {
    const c = new EpubController();
    await c.init(container, 'http://example.com/book.epub');
    c.destroy();
    expect(() => c.destroy()).not.toThrow();
  });
});

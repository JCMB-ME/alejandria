/**
 * PdfController unit test (Phase D, item D10c).
 *
 * Mocks pdfjs-dist so we don't need a real PDF file. Verifies the
 * controller's surface (clamping, destroy, scale).
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

// Mock pdfjs-dist with a 10-page fake PDF document.
const mockGetPage = vi.fn((n: number) => Promise.resolve({
  getViewport: ({ scale }: { scale: number }) => ({
    width: 800 * scale,
    height: 1200 * scale,
  }),
  render: () => ({ promise: Promise.resolve() }),
}));

const mockPdfDoc = {
  numPages: 10,
  getPage: mockGetPage,
  destroy: vi.fn(),
};

vi.mock('pdfjs-dist', () => ({
  default: {
    GlobalWorkerOptions: { workerSrc: '' },
    getDocument: () => ({ promise: Promise.resolve(mockPdfDoc) }),
  },
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: () => ({ promise: Promise.resolve(mockPdfDoc) }),
}));

// jsdom doesn't provide visualViewport; polyfill it.
if (typeof window !== 'undefined' && !window.visualViewport) {
  (window as any).visualViewport = {
    addEventListener: () => {},
    removeEventListener: () => {},
  };
}

import { PdfController } from './PdfController.svelte';

describe('PdfController', () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    vi.clearAllMocks();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  it('init() resolves and reports totalPages', async () => {
    const c = new PdfController();
    await c.init(container, 'http://example.com/book.pdf', { containerWidth: 800 });
    expect(c.ready).toBe(true);
    expect(c.totalPages).toBe(10);
    expect(c.canGoToPage).toBe(true);
    c.destroy();
  });

  it('next() advances currentPage', async () => {
    const c = new PdfController();
    await c.init(container, 'http://example.com/book.pdf', { containerWidth: 800 });
    await c.next();
    expect(c.currentPage).toBe(2);
    c.destroy();
  });

  it('goToPage(99) clamps to 10', async () => {
    const c = new PdfController();
    await c.init(container, 'http://example.com/book.pdf', { containerWidth: 800 });
    await c.goToPage(99);
    expect(c.currentPage).toBe(10);
    c.destroy();
  });

  it('destroy() is idempotent', async () => {
    const c = new PdfController();
    await c.init(container, 'http://example.com/book.pdf', { containerWidth: 800 });
    c.destroy();
    expect(() => c.destroy()).not.toThrow();
  });
});

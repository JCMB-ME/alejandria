/**
 * CbzController unit test (Phase D, item D10d).
 *
 * Mocks jszip and fetch to inject a 3-image mock CBZ. Verifies the
 * controller's surface (clamping, destroy revokes URLs).
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

// Build a small fake PNG blob (just enough bytes — the test never
// decodes it, only checks the controller's bookkeeping).
function makePngBytes(seed: number): Uint8Array {
  const arr = new Uint8Array(64);
  for (let i = 0; i < arr.length; i++) arr[i] = (i + seed) & 0xff;
  return arr;
}

const mockEntries = [
  { name: 'page-1.png', dir: false, async: () => Promise.resolve(new Blob([makePngBytes(1)], { type: 'image/png' })) },
  { name: 'page-2.png', dir: false, async: () => Promise.resolve(new Blob([makePngBytes(2)], { type: 'image/png' })) },
  { name: 'page-3.png', dir: false, async: () => Promise.resolve(new Blob([makePngBytes(3)], { type: 'image/png' })) },
];

const mockZip = {
  files: {
    'page-1.png': mockEntries[0],
    'page-2.png': mockEntries[1],
    'page-3.png': mockEntries[2],
  },
};

vi.mock('jszip', () => ({
  default: {
    loadAsync: () => Promise.resolve(mockZip),
  },
}));

import { CbzController } from './CbzController.svelte';

describe('CbzController', () => {
  let container: HTMLDivElement;
  let revokeSpy: any;
  let createSpy: any;

  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom may not have URL.createObjectURL/revokeObjectURL — stub
    // them so the controller can use them.
    if (typeof URL.createObjectURL !== 'function') {
      (URL as any).createObjectURL = () => 'blob:fake';
    }
    if (typeof URL.revokeObjectURL !== 'function') {
      (URL as any).revokeObjectURL = () => {};
    }
    revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    createSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake');
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true,
      arrayBuffer: () => Promise.resolve(new ArrayBuffer(8)),
    })));
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    if (container.parentNode) document.body.removeChild(container);
    revokeSpy.mockRestore();
    createSpy.mockRestore();
    vi.unstubAllGlobals();
  });

  it('init() decodes 3 pages', async () => {
    const c = new CbzController();
    await c.init(container, 'http://example.com/book.cbz');
    expect(c.ready).toBe(true);
    expect(c.totalPages).toBe(3);
    c.destroy();
  });

  it('next() advances currentPage', async () => {
    const c = new CbzController();
    await c.init(container, 'http://example.com/book.cbz');
    await c.next();
    expect(c.currentPage).toBe(2);
    c.destroy();
  });

  it('goToPage(0) clamps to 1', async () => {
    const c = new CbzController();
    await c.init(container, 'http://example.com/book.cbz');
    await c.goToPage(0);
    expect(c.currentPage).toBe(1);
    c.destroy();
  });

  it('destroy() revokes all object URLs', async () => {
    const c = new CbzController();
    await c.init(container, 'http://example.com/book.cbz');
    c.destroy();
    // 3 pages → 3 object URLs created → 3 revokes.
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(3);
  });
});

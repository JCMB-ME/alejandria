/**
 * TextController unit test (Phase D, item D10e).
 *
 * Exercises the simple text reader (FB2 / RTF / TXT) with a stubbed
 * `fetch`. No real EPUB/PDF/CBZ deps; this is the simplest of the
 * four controllers.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TextController } from './TextController.svelte';

describe('TextController', () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('init() resolves and renders paragraphs', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      text: () => Promise.resolve('paragraph one\n\nparagraph two'),
    })));

    const c = new TextController();
    await c.init(container, 'http://example.com/book.txt');

    expect(c.ready).toBe(true);
    const reader = container.querySelector('div.reader');
    expect(reader).toBeTruthy();
    expect(reader!.querySelectorAll('p').length).toBe(2);

    c.destroy();
    vi.unstubAllGlobals();
  });

  it('next/prev/goToPage are no-ops', async () => {
    const c = new TextController();
    await c.next();
    await c.prev();
    await c.goToPage(5);
    expect(c.currentPage).toBe(1);
  });

  it('createHighlight returns null', async () => {
    const c = new TextController();
    expect(await c.createHighlight('yellow')).toBeNull();
  });

  it('destroy() is idempotent', async () => {
    const c = new TextController();
    c.destroy();
    expect(() => c.destroy()).not.toThrow();
  });
});

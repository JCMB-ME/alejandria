/**
 * ReaderController interface contract test (Phase D, item D10a).
 *
 * Smoke-checks that every concrete controller implements the full
 * interface surface. Catches future regressions if someone narrows
 * the interface.
 */
import { describe, it, expect } from 'vitest';
import { createControllerFor } from './factory';
import type { ReaderController } from './types';

const METHOD_NAMES: (keyof ReaderController)[] = [
  'init', 'destroy', 'next', 'prev', 'goToPage', 'goToHighlight',
  'goToToc', 'createHighlight', 'deleteHighlight', 'getHighlights',
  'applyHighlights', 'setFontSize', 'setFontFamily', 'setLineHeight',
  'setTheme', 'on',
];

describe('ReaderController interface contract', () => {
  it('factory returns an instance of every format', () => {
    expect(createControllerFor('epub')).toBeTruthy();
    expect(createControllerFor('pdf')).toBeTruthy();
    expect(createControllerFor('cbz')).toBeTruthy();
    expect(createControllerFor('fb2')).toBeTruthy();
    expect(createControllerFor('rtf')).toBeTruthy();
    expect(createControllerFor('txt')).toBeTruthy();
  });

  it('every concrete controller implements the full interface', () => {
    for (const fmt of ['epub', 'pdf', 'cbz', 'fb2', 'rtf', 'txt'] as const) {
      const c = createControllerFor(fmt);
      for (const m of METHOD_NAMES) {
        expect(typeof (c as any)[m]).toBe('function');
      }
    }
  });

  it('on() returns an unsubscribe function', () => {
    const c = createControllerFor('txt');
    const unsub = c.on('ready', () => {});
    expect(typeof unsub).toBe('function');
    expect(() => unsub()).not.toThrow();
  });

  it('controllers start with safe defaults', () => {
    for (const fmt of ['epub', 'pdf', 'cbz', 'fb2', 'rtf', 'txt'] as const) {
      const c = createControllerFor(fmt);
      expect(typeof c.currentPage).toBe('number');
      expect(typeof c.totalPages).toBe('number');
      expect(typeof c.currentProgress).toBe('number');
      expect(typeof c.ready).toBe('boolean');
      expect(typeof c.canGoToPage).toBe('boolean');
      expect(typeof c.canHighlight).toBe('boolean');
    }
  });
});

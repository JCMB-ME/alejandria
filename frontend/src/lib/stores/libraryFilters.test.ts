/**
 * Vitest tests for the libraryFilters store (Plan 2).
 *
 * Pure unit tests — no DOM, no Svelte runtime required.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import {
  libraryFilters,
  updateFilters,
  clearFilters,
  toUrlParams,
  fromUrlParams,
  activeFilterCount,
  DEFAULT_FILTERS,
} from './libraryFilters';

describe('libraryFilters store', () => {
  beforeEach(() => {
    clearFilters();
  });

  it('starts at the default state', () => {
    const s = get(libraryFilters);
    expect(s).toEqual(DEFAULT_FILTERS);
  });

  it('updateFilters applies a partial patch', () => {
    updateFilters({ sort: 'pubdate', order: 'desc' });
    const s = get(libraryFilters);
    expect(s.sort).toBe('pubdate');
    expect(s.order).toBe('desc');
    // Other fields untouched
    expect(s.page).toBe(1);
    expect(s.authors).toEqual([]);
  });

  it('clearFilters returns to defaults', () => {
    updateFilters({ sort: 'timestamp', authors: [1, 2] });
    clearFilters();
    expect(get(libraryFilters)).toEqual(DEFAULT_FILTERS);
  });

  it('toUrlParams serializes the active fields', () => {
    updateFilters({
      authors: [1, 2],
      tags: [5],
      formats: ['EPUB'],
      sort: 'pubdate',
      order: 'desc',
      page: 3,
    });
    const q = toUrlParams(get(libraryFilters));
    expect(q.getAll('author')).toEqual(['1', '2']);
    expect(q.getAll('tag')).toEqual(['5']);
    expect(q.get('format')).toBe('EPUB');
    expect(q.get('sort')).toBe('pubdate');
    expect(q.get('order')).toBe('desc');
    expect(q.get('page')).toBe('3');
  });

  it('toUrlParams omits default values', () => {
    const q = toUrlParams(DEFAULT_FILTERS);
    expect(q.has('sort')).toBe(false);
    expect(q.has('order')).toBe(false);
    expect(q.has('page')).toBe(false);
    expect(q.has('author')).toBe(false);
  });

  it('fromUrlParams parses multi-value keys', () => {
    const q = new URLSearchParams('author=1&author=2&tag=3&format=PDF&sort=timestamp');
    const s = fromUrlParams(q);
    expect(s.authors).toEqual([1, 2]);
    expect(s.tags).toEqual([3]);
    expect(s.formats).toEqual(['PDF']);
    expect(s.sort).toBe('timestamp');
    expect(s.order).toBe('asc'); // default
    expect(s.page).toBe(1); // default
  });

  it('fromUrlParams ignores unknown params', () => {
    const q = new URLSearchParams('garbage=1&author=5');
    const s = fromUrlParams(q);
    expect(s.authors).toEqual([5]);
    // 'garbage' silently ignored
  });

  it('fromUrlParams + toUrlParams round-trip', () => {
    const original = {
      ...DEFAULT_FILTERS,
      authors: [1, 2],
      tags: [9],
      formats: ['EPUB', 'PDF'],
      languages: ['en', 'es'],
      addedAfter: '2024-01-01',
      addedBefore: '2024-12-31',
      sort: 'last_read',
      order: 'desc' as const,
      search: 'foo',
      page: 5,
    };
    const serialized = toUrlParams(original);
    const parsed = fromUrlParams(serialized);
    expect(parsed).toEqual(original);
  });

  it('activeFilterCount counts only non-default fields', () => {
    expect(activeFilterCount(DEFAULT_FILTERS)).toBe(0);
    updateFilters({ authors: [1, 2] });
    expect(activeFilterCount(get(libraryFilters))).toBe(2);
    updateFilters({ formats: ['EPUB'] });
    expect(activeFilterCount(get(libraryFilters))).toBe(3);
    updateFilters({ addedAfter: '2024-01-01' });
    expect(activeFilterCount(get(libraryFilters))).toBe(4);
    updateFilters({ search: 'hello' });
    expect(activeFilterCount(get(libraryFilters))).toBe(5);
  });
});

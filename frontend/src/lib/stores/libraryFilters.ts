/**
 * Library filters store — bound to URL state.
 *
 * F3 + F7: the filter state is the URL; the URL is the filter state.
 * State -> URL: debounced `history.replaceState` (200ms).
 * URL    -> State: read on store construction + on every page-store tick.
 *
 * The librarySelection store subscribes to `page` and clears itself on
 * URL change — implementing "filters persist across reload/back; selection
 * is ephemeral" (per F7 in the plan).
 */

import { writable, get, type Writable } from 'svelte/store';
import { browser } from '$app/environment';

export interface LibraryFiltersState {
  authors: number[];
  tags: number[];
  series: number[];
  formats: string[];
  languages: string[];
  addedAfter: string | null;
  addedBefore: string | null;
  sort: string;
  order: 'asc' | 'desc';
  search: string;
  page: number;
}

export const DEFAULT_FILTERS: LibraryFiltersState = {
  authors: [],
  tags: [],
  series: [],
  formats: [],
  languages: [],
  addedAfter: null,
  addedBefore: null,
  sort: 'sort_title',
  order: 'asc',
  search: '',
  page: 1,
};

const _state: Writable<LibraryFiltersState> = writable({ ...DEFAULT_FILTERS });

/** Read a value from the store. */
export const libraryFilters = { subscribe: _state.subscribe };

/** Apply a partial update to the state. */
export function updateFilters(patch: Partial<LibraryFiltersState>): void {
  _state.update((s) => ({ ...s, ...patch }));
}

/** Reset the state to defaults. */
export function clearFilters(): void {
  _state.set({ ...DEFAULT_FILTERS });
}

/** Number of distinct, active filters (used for the badge on the filter button). */
export function activeFilterCount(s: LibraryFiltersState): number {
  let n = 0;
  if (s.authors.length) n += s.authors.length;
  if (s.tags.length) n += s.tags.length;
  if (s.series.length) n += s.series.length;
  if (s.formats.length) n += s.formats.length;
  if (s.languages.length) n += s.languages.length;
  if (s.addedAfter) n += 1;
  if (s.addedBefore) n += 1;
  if (s.search) n += 1;
  return n;
}

// ---------------------------------------------------------------------------
// URL <-> state
// ---------------------------------------------------------------------------

/** Convert a LibraryFiltersState to a URLSearchParams object. */
export function toUrlParams(s: LibraryFiltersState): URLSearchParams {
  const q = new URLSearchParams();
  for (const a of s.authors) q.append('author', String(a));
  for (const t of s.tags) q.append('tag', String(t));
  for (const se of s.series) q.append('series', String(se));
  for (const f of s.formats) q.append('format', f);
  for (const l of s.languages) q.append('language', l);
  if (s.addedAfter) q.set('added_after', s.addedAfter);
  if (s.addedBefore) q.set('added_before', s.addedBefore);
  if (s.search) q.set('search', s.search);
  if (s.sort !== DEFAULT_FILTERS.sort) q.set('sort', s.sort);
  if (s.order !== DEFAULT_FILTERS.order) q.set('order', s.order);
  if (s.page !== 1) q.set('page', String(s.page));
  return q;
}

/** Convert a URLSearchParams (or a generic record) to a LibraryFiltersState. */
export function fromUrlParams(input: URLSearchParams | Record<string, string | string[]>): LibraryFiltersState {
  const get = (k: string): string[] => {
    if (input instanceof URLSearchParams) {
      return input.getAll(k);
    }
    const v = input[k];
    if (v === undefined) return [];
    return Array.isArray(v) ? v : [v];
  };
  const one = (k: string): string | null => {
    if (input instanceof URLSearchParams) return input.get(k);
    const v = input[k];
    if (v === undefined) return null;
    return Array.isArray(v) ? (v[0] ?? null) : v;
  };
  const toInt = (s: string | null): number | null => {
    if (s === null || s === '') return null;
    const n = parseInt(s, 10);
    return Number.isFinite(n) ? n : null;
  };
  return {
    authors: get('author').map((s) => parseInt(s, 10)).filter(Number.isFinite),
    tags: get('tag').map((s) => parseInt(s, 10)).filter(Number.isFinite),
    series: get('series').map((s) => parseInt(s, 10)).filter(Number.isFinite),
    formats: get('format'),
    languages: get('language'),
    addedAfter: one('added_after'),
    addedBefore: one('added_before'),
    sort: one('sort') || DEFAULT_FILTERS.sort,
    order: (one('order') === 'desc' ? 'desc' : 'asc'),
    search: one('search') || '',
    page: toInt(one('page')) ?? 1,
  };
}

// ---------------------------------------------------------------------------
// Two-way binding
// ---------------------------------------------------------------------------

let _initialized = false;
let _writingFromUrl = false;
let _writingFromState = false;
let _debounceTimer: ReturnType<typeof setTimeout> | null = null;

/** Initialize the URL <-> store wiring. Call from a top-level component. */
export function initLibraryFiltersBinding(): void {
  if (!browser || _initialized) return;
  _initialized = true;
  // Dynamic import so vitest (no SvelteKit) can load the store without
  // resolving $app/stores at module-evaluation time.
  void import('$app/stores').then(({ page }) => {
    // Read once on init
    const current = get(page).url;
    _writingFromUrl = true;
    _state.set(fromUrlParams(current.searchParams));
    _writingFromUrl = false;

    // URL -> state (on every SvelteKit navigation, including back/forward)
    page.subscribe((p) => {
      if (!browser) return;
      const next = fromUrlParams(p.url.searchParams);
      const cur = get(_state);
      if (shallowEqualFilters(cur, next)) return;
      _writingFromUrl = true;
      _state.set(next);
      _writingFromUrl = false;
    });
  });

  // State -> URL (debounced)
  _state.subscribe((s) => {
    if (_writingFromUrl) return;
    if (_debounceTimer) clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(() => {
      const u = new URL(window.location.href);
      u.search = toUrlParams(s).toString();
      // Only push if the URL would actually change
      if (u.toString() !== window.location.href) {
        window.history.replaceState(window.history.state, '', u.toString());
      }
    }, 200);
  });
}

function shallowEqualFilters(a: LibraryFiltersState, b: LibraryFiltersState): boolean {
  return (
    a.sort === b.sort &&
    a.order === b.order &&
    a.search === b.search &&
    a.page === b.page &&
    a.addedAfter === b.addedAfter &&
    a.addedBefore === b.addedBefore &&
    arrEq(a.authors, b.authors) &&
    arrEq(a.tags, b.tags) &&
    arrEq(a.series, b.series) &&
    arrEq(a.formats, b.formats) &&
    arrEq(a.languages, b.languages)
  );
}

function arrEq(a: readonly (string | number)[], b: readonly (string | number)[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

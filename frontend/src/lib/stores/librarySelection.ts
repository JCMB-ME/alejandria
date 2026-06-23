/**
 * Library selection store — ephemeral Set<number> of selected book ids.
 *
 * F6: multi-select on the library page.
 * F7: selection is NOT in the URL; on URL change (filter navigation,
 *     back button, refresh), the selection clears. This is the
 *     established pattern: filters are persistent (URL), selection is
 *     ephemeral (memory).
 */

import { writable, get, type Writable } from 'svelte/store';
import { browser } from '$app/environment';

const _state: Writable<Set<number>> = writable(new Set());

/** Subscribe to the selection set. */
export const librarySelection = { subscribe: _state.subscribe };

/** Number of selected book ids. */
export const selectedCount = { subscribe: (run: (n: number) => void) => _state.subscribe((s) => run(s.size)) };

/** Toggle one book id. */
export function toggleSelected(id: number): void {
  _state.update((s) => {
    const next = new Set(s);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });
}

/** Add a book id to the selection. */
export function addSelected(id: number): void {
  _state.update((s) => {
    if (s.has(id)) return s;
    const next = new Set(s);
    next.add(id);
    return next;
  });
}

/** Remove a book id from the selection. */
export function removeSelected(id: number): void {
  _state.update((s) => {
    if (!s.has(id)) return s;
    const next = new Set(s);
    next.delete(id);
    return next;
  });
}

/** Clear the entire selection. */
export function clearSelection(): void {
  _state.set(new Set());
}

/** Replace the selection with the given list. */
export function setSelectedAll(ids: number[]): void {
  _state.set(new Set(ids));
}

/** Test whether a book id is currently selected. */
export function isSelected(id: number): boolean {
  return get(_state).has(id);
}

/** Snapshot the selection as a sorted array of ids. */
export function selectedIds(): number[] {
  return Array.from(get(_state)).sort((a, b) => a - b);
}

// ---------------------------------------------------------------------------
// URL -> "clear selection" (F7)
// ---------------------------------------------------------------------------

let _initialized = false;
let _lastUrl = '';

export function initLibrarySelectionBinding(): void {
  if (!browser || _initialized) return;
  _initialized = true;

  _lastUrl = window.location.href;
  // Dynamic import so vitest (no SvelteKit) can load this module without
  // resolving $app/stores at module-evaluation time.
  void import('$app/stores').then(({ page }) => {
    page.subscribe(() => {
      if (!browser) return;
      if (window.location.href !== _lastUrl) {
        _lastUrl = window.location.href;
        // URL changed (filter nav, back button, browser forward).
        // Selection is ephemeral — clear it.
        clearSelection();
      }
    });
  });
}

/**
 * Vitest tests for FilterCheckboxList (Plan 2 — filter UI rework).
 *
 * The toggle / remove logic lives in `./filterCheckboxLogic` (pure
 * functions) so we can unit-test the behaviour without mounting a
 * Svelte component — matches the existing test pattern in the repo.
 */

import { describe, it, expect } from 'vitest';
import {
  type FilterOption,
  keyOf,
  isSelected,
  toggle as toggleSelection,
  remove as removeSelection,
} from './filterCheckboxLogic';

const authorOptions: FilterOption[] = [
  { id: 1, name: 'Ursula K. Le Guin', count: 7 },
  { id: 2, name: 'Isaac Asimov', count: 12 },
  { id: 3, name: 'Octavia Butler', count: 4 },
];

const formatOptions: FilterOption[] = [
  { name: 'EPUB', count: 30 },
  { name: 'PDF', count: 5 },
  { name: 'MOBI', count: 2 },
];

describe('FilterCheckboxList logic — byId (authors/tags/series)', () => {
  it('keyOf returns the numeric id', () => {
    expect(keyOf(authorOptions[0], 'byId')).toBe(1);
    expect(keyOf(authorOptions[2], 'byId')).toBe(3);
  });

  it('keyOf falls back to the name when id is missing', () => {
    const o: FilterOption = { name: 'no-id', count: 1 };
    expect(keyOf(o, 'byId')).toBe('no-id');
  });

  it('isSelected returns true for matching ids and false otherwise', () => {
    expect(isSelected([2], authorOptions[1], 'byId')).toBe(true);
    expect(isSelected([1, 3], authorOptions[1], 'byId')).toBe(false);
    expect(isSelected([], authorOptions[0], 'byId')).toBe(false);
  });

  it('toggle adds the id when not currently selected', () => {
    const next = toggleSelection([], authorOptions[1], 'byId');
    expect(next).toEqual([2]);
  });

  it('toggle removes the id when currently selected', () => {
    const next = toggleSelection([1, 2, 3], authorOptions[1], 'byId');
    expect(next).toEqual([1, 3]);
  });

  it('toggle preserves selection order and does not duplicate', () => {
    const next = toggleSelection([1, 2], authorOptions[1], 'byId');
    expect(next).toEqual([1]);
    const next2 = toggleSelection([1], authorOptions[1], 'byId');
    expect(next2).toEqual([1, 2]);
  });

  it('remove returns a new array with the matching id filtered out', () => {
    const next = removeSelection([1, 2, 3], 2, 'byId');
    expect(next).toEqual([1, 3]);
  });

  it('remove is a no-op when the key is not in the selection', () => {
    const next = removeSelection([1, 2], 99, 'byId');
    expect(next).toEqual([1, 2]);
  });
});

describe('FilterCheckboxList logic — byName (formats/languages)', () => {
  it('keyOf returns the option name', () => {
    expect(keyOf(formatOptions[0], 'byName')).toBe('EPUB');
    expect(keyOf(formatOptions[2], 'byName')).toBe('MOBI');
  });

  it('isSelected matches on string equality', () => {
    expect(isSelected(['EPUB'], formatOptions[0], 'byName')).toBe(true);
    expect(isSelected(['PDF', 'MOBI'], formatOptions[0], 'byName')).toBe(false);
  });

  it('toggle adds the name when not currently selected', () => {
    const next = toggleSelection([], formatOptions[0], 'byName');
    expect(next).toEqual(['EPUB']);
  });

  it('toggle removes the name when currently selected', () => {
    const next = toggleSelection(['EPUB', 'PDF'], formatOptions[0], 'byName');
    expect(next).toEqual(['PDF']);
  });

  it('remove filters by name string equality', () => {
    const next = removeSelection(['EPUB', 'PDF', 'MOBI'], 'PDF', 'byName');
    expect(next).toEqual(['EPUB', 'MOBI']);
  });
});

describe('FilterCheckboxList — component contract (text snapshot)', () => {
  /**
   * Minimal sanity check: the Svelte template is wired such that the
   * checkbox `checked` attribute follows `isSelected`, the `onchange`
   * handler calls `toggleSelection`, and the chip remove button calls
   * `removeSelection`. We don't mount the component (no DOM setup for
   * Svelte 5 in the existing test config) — instead we confirm the
   * behaviour via the helpers.
   */
  it('emits the expected onChange payloads for a typical session', () => {
    let selected: Array<number | string> = [];

    // User clicks "Isaac Asimov"
    selected = toggleSelection(selected, authorOptions[1], 'byId');
    expect(selected).toEqual([2]);

    // User clicks "Octavia Butler"
    selected = toggleSelection(selected, authorOptions[2], 'byId');
    expect(selected).toEqual([2, 3]);

    // User removes the "Isaac Asimov" chip
    selected = removeSelection(selected, 2, 'byId');
    expect(selected).toEqual([3]);

    // User re-selects Isaac
    selected = toggleSelection(selected, authorOptions[1], 'byId');
    expect(selected).toEqual([3, 2]);
  });

  it('emits the expected onChange payloads for a byName session', () => {
    let selected: Array<number | string> = [];
    selected = toggleSelection(selected, formatOptions[0], 'byName');
    selected = toggleSelection(selected, formatOptions[2], 'byName');
    expect(selected).toEqual(['EPUB', 'MOBI']);
    selected = removeSelection(selected, 'EPUB', 'byName');
    expect(selected).toEqual(['MOBI']);
  });
});

/**
 * Vitest tests for the librarySelection store (Plan 2).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import {
  librarySelection,
  selectedCount,
  toggleSelected,
  addSelected,
  removeSelected,
  clearSelection,
  setSelectedAll,
  isSelected,
  selectedIds,
} from './librarySelection';

describe('librarySelection store', () => {
  beforeEach(() => {
    clearSelection();
  });

  it('starts empty', () => {
    expect(get(librarySelection).size).toBe(0);
    expect(get(selectedCount)).toBe(0);
  });

  it('toggleSelected adds then removes', () => {
    toggleSelected(1);
    expect(get(librarySelection).has(1)).toBe(true);
    expect(get(selectedCount)).toBe(1);
    toggleSelected(1);
    expect(get(librarySelection).has(1)).toBe(false);
    expect(get(selectedCount)).toBe(0);
  });

  it('addSelected is idempotent', () => {
    addSelected(5);
    addSelected(5);
    expect(get(selectedCount)).toBe(1);
  });

  it('removeSelected is a no-op when missing', () => {
    removeSelected(5);
    expect(get(selectedCount)).toBe(0);
    addSelected(5);
    removeSelected(5);
    expect(get(selectedCount)).toBe(0);
  });

  it('clearSelection empties the set', () => {
    addSelected(1);
    addSelected(2);
    addSelected(3);
    expect(get(selectedCount)).toBe(3);
    clearSelection();
    expect(get(selectedCount)).toBe(0);
  });

  it('setSelectedAll replaces the set', () => {
    addSelected(99);
    setSelectedAll([1, 2, 3]);
    const set = get(librarySelection);
    expect(set.size).toBe(3);
    expect(set.has(99)).toBe(false);
    expect(set.has(1)).toBe(true);
  });

  it('isSelected is a snapshot helper', () => {
    addSelected(7);
    expect(isSelected(7)).toBe(true);
    expect(isSelected(8)).toBe(false);
  });

  it('selectedIds returns sorted ids', () => {
    setSelectedAll([3, 1, 2]);
    expect(selectedIds()).toEqual([1, 2, 3]);
  });
});

/**
 * Pure toggle / remove helpers for the filter checkbox list.
 *
 * Extracted so the logic can be unit-tested without mounting Svelte
 * (matches the existing test pattern in the repo, which doesn't render
 * .svelte files).
 */

export type FilterMode = 'byId' | 'byName';

export interface FilterOption {
  id?: number;
  name: string;
  count: number;
}

export function keyOf(opt: FilterOption, mode: FilterMode): number | string {
  if (mode === 'byId') {
    if (opt.id === undefined || opt.id === null) return opt.name;
    return opt.id;
  }
  return opt.name;
}

export function isSelected(
  selected: Array<number | string>,
  opt: FilterOption,
  mode: FilterMode,
): boolean {
  const k = keyOf(opt, mode);
  if (mode === 'byId') {
    return selected.some((s) => Number(s) === Number(k));
  }
  return selected.some((s) => String(s) === String(k));
}

export function toggle(
  selected: Array<number | string>,
  opt: FilterOption,
  mode: FilterMode,
): Array<number | string> {
  const k = keyOf(opt, mode);
  if (isSelected(selected, opt, mode)) {
    if (mode === 'byId') {
      return selected.filter((s) => Number(s) !== Number(k));
    }
    return selected.filter((s) => String(s) !== String(k));
  }
  return [...selected, k];
}

export function remove(
  selected: Array<number | string>,
  k: number | string,
  mode: FilterMode,
): Array<number | string> {
  if (mode === 'byId') {
    return selected.filter((s) => Number(s) !== Number(k));
  }
  return selected.filter((s) => String(s) !== String(k));
}

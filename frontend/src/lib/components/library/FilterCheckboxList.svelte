<script lang="ts">
  import { t } from '$stores/i18n';
  import {
    type FilterOption,
    type FilterMode,
    keyOf,
    isSelected,
    toggle as toggleSelection,
    remove as removeSelection,
  } from './filterCheckboxLogic';

  /**
   * Reusable checkbox list for a single multi-select filter field.
   *
   * - Authors / tags / series: keyed by numeric `id`.
   * - Formats / languages: keyed by string `name`.
   *
   * Selected items render as removable chips above the list.
   * Each row is a `<label>` so clicking anywhere toggles the checkbox.
   */

  interface Props {
    options: FilterOption[];
    selected: Array<number | string>;
    label: string;
    mode: FilterMode;
    onChange: (newSelection: Array<number | string>) => void;
  }

  let { options, selected, label, mode, onChange }: Props = $props();

  function toggle(opt: FilterOption) {
    onChange(toggleSelection(selected, opt, mode));
  }

  function removeKey(k: number | string) {
    onChange(removeSelection(selected, k, mode));
  }

  function optionForKey(k: number | string): FilterOption | undefined {
    if (mode === 'byId') {
      return options.find((o) => Number(o.id) === Number(k));
    }
    return options.find((o) => o.name === String(k));
  }

  function displayFor(k: number | string): string {
    const o = optionForKey(k);
    return o ? o.name : String(k);
  }
</script>

<div class="flex flex-col gap-1.5">
  <span class="text-xs text-[var(--text-muted)]">{label}</span>

  {#if selected.length > 0}
    <div class="flex flex-wrap gap-1.5" data-testid="chips">
      {#each selected as k (mode === 'byId' ? `id-${k}` : `name-${k}`)}
        <span
          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border"
          style="background: color-mix(in srgb, var(--accent) 10%, transparent); border-color: color-mix(in srgb, var(--accent) 30%, var(--border)); color: var(--text);"
        >
          <span class="font-medium">{displayFor(k)}</span>
          <button
            type="button"
            class="ml-0.5 -mr-1 inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            aria-label={`${$t('filter_remove')}: ${displayFor(k)}`}
            onclick={() => removeKey(k)}
            data-testid="chip-remove"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
              <line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/>
            </svg>
          </button>
        </span>
      {/each}
    </div>
  {/if}

  {#if options.length === 0}
    <div class="text-xs text-[var(--text-muted)] py-1">{$t('filter_empty')}</div>
  {:else}
    <ul
      class="flex flex-col gap-0.5 overflow-y-auto max-h-48 pr-1"
      style="border: 1px solid var(--border); border-radius: 0.375rem; background: var(--surface);"
      role="listbox"
      aria-multiselectable="true"
      aria-label={label}
    >
      {#each options as opt (mode === 'byId' && opt.id !== undefined ? opt.id : opt.name)}
        <li>
          <label
            class="flex items-center gap-2 px-2 py-1.5 text-xs cursor-pointer hover:bg-[var(--surface-hover)] rounded"
          >
            <input
              type="checkbox"
              class="accent-[var(--accent)]"
              checked={isSelected(selected, opt, mode)}
              onchange={() => toggle(opt)}
              aria-label={opt.name}
              data-testid="checkbox-row"
            />
            <span class="flex-1 truncate">{opt.name}</span>
            <span class="text-[var(--text-muted)] tabular-nums">({opt.count})</span>
          </label>
        </li>
      {/each}
    </ul>
  {/if}
</div>

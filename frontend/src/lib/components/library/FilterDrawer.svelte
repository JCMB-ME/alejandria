<script lang="ts">
  import { t } from '$stores/i18n';
  import FilterBar from './FilterBar.svelte';
  import { clearFilters, activeFilterCount, type LibraryFiltersState } from '$stores/libraryFilters';
  import type { FilterOptions } from '$api/types';

  interface Props {
    open: boolean;
    options: FilterOptions | null;
    state: LibraryFiltersState;
    resultCount: number;
    onClose: () => void;
  }
  let { open, options, state, resultCount, onClose }: Props = $props();

  // Lock body scroll when open
  $effect(() => {
    if (open && typeof document !== 'undefined') {
      const prev = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = prev;
      };
    }
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) onClose();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <div
    class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm lg:hidden"
    role="dialog"
    aria-modal="true"
    aria-labelledby="filter-drawer-title"
    tabindex="-1"
    onclick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    onkeydown={handleKeydown}
  >
    <div
      class="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-2xl p-5 shadow-2xl"
      style="background: var(--surface); border-top: 1px solid var(--border);"
    >
      <div class="flex items-center justify-between mb-4">
        <h2 id="filter-drawer-title" class="text-lg font-semibold">
          {$t('filter_drawer_title')}
          <span class="text-sm font-normal text-[var(--text-muted)] ml-2">
            {$t(resultCount === 1 ? 'filter_results' : 'filter_results_plural', { n: resultCount })}
          </span>
        </h2>
        <button
          type="button"
          class="w-8 h-8 inline-flex items-center justify-center rounded-full hover:bg-[var(--surface-hover)]"
          aria-label="Close"
          onclick={onClose}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/>
          </svg>
        </button>
      </div>

      <FilterBar {options} {state} mode="drawer" />

      <div class="mt-5 flex justify-end gap-2 border-t pt-4" style="border-color: var(--border);">
        <button type="button" class="btn btn-ghost" onclick={clearFilters}>
          {$t('filter_clear_all')}
        </button>
        <button type="button" class="btn btn-primary" onclick={onClose}>
          {$t('bulk_apply')} ({resultCount})
        </button>
      </div>
    </div>
  </div>
{/if}

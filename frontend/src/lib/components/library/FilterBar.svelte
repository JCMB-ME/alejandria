<script lang="ts">
  import FilterChip from './FilterChip.svelte';
  import FilterCheckboxList from './FilterCheckboxList.svelte';
  import { t } from '$stores/i18n';
  import { updateFilters, clearFilters, type LibraryFiltersState } from '$stores/libraryFilters';
  import type { FilterOptions } from '$api/types';

  interface Props {
    options: FilterOptions | null;
    state: LibraryFiltersState;
    mode: 'sidebar' | 'drawer';
  }
  let { options, state, mode }: Props = $props();

  function setAuthors(v: Array<number | string>) {
    updateFilters({ authors: v as number[], page: 1 });
  }
  function setTags(v: Array<number | string>) {
    updateFilters({ tags: v as number[], page: 1 });
  }
  function setSeries(v: Array<number | string>) {
    updateFilters({ series: v as number[], page: 1 });
  }
  function setFormats(v: Array<number | string>) {
    updateFilters({ formats: v as string[], page: 1 });
  }
  function setLanguages(v: Array<number | string>) {
    updateFilters({ languages: v as string[], page: 1 });
  }

  // Date/search chips still need to surface in the global "active filters"
  // section (they have no checkbox list).
  const hasNonListFilters = $derived(
    Boolean(state.addedAfter || state.addedBefore || state.search)
  );
</script>

<div
  class="{mode === 'drawer' ? 'flex flex-col gap-4' : 'flex flex-col gap-4'}"
>
  {#if hasNonListFilters}
    <div>
      <div class="text-xs text-[var(--text-muted)] mb-2">{$t('filter_active')}</div>
      <div class="flex flex-wrap gap-1.5">
        {#if state.addedAfter}
          <FilterChip
            label={$t('filter_added_after')}
            value={state.addedAfter}
            onRemove={() => updateFilters({ addedAfter: null, page: 1 })}
          />
        {/if}
        {#if state.addedBefore}
          <FilterChip
            label={$t('filter_added_before')}
            value={state.addedBefore}
            onRemove={() => updateFilters({ addedBefore: null, page: 1 })}
          />
        {/if}
        {#if state.search}
          <FilterChip
            label="search"
            value={state.search}
            onRemove={() => updateFilters({ search: '', page: 1 })}
          />
        {/if}
        <button
          type="button"
          class="text-xs underline text-[var(--text-muted)] hover:text-[var(--text)] self-center"
          onclick={() => clearFilters()}
        >
          {$t('filter_clear_all')}
        </button>
      </div>
    </div>
  {/if}

  <div class="grid grid-cols-1 gap-3">
    <FilterCheckboxList
      options={options?.authors ?? []}
      selected={state.authors}
      label={$t('filter_author')}
      mode="byId"
      onChange={setAuthors}
    />

    <FilterCheckboxList
      options={options?.tags ?? []}
      selected={state.tags}
      label={$t('filter_tag')}
      mode="byId"
      onChange={setTags}
    />

    <FilterCheckboxList
      options={options?.series ?? []}
      selected={state.series}
      label={$t('filter_series')}
      mode="byId"
      onChange={setSeries}
    />

    <FilterCheckboxList
      options={options?.formats ?? []}
      selected={state.formats}
      label={$t('filter_format')}
      mode="byName"
      onChange={setFormats}
    />

    <FilterCheckboxList
      options={options?.languages ?? []}
      selected={state.languages}
      label={$t('filter_language')}
      mode="byName"
      onChange={setLanguages}
    />

    <div class="grid grid-cols-2 gap-2">
      <label class="flex flex-col gap-1">
        <span class="text-xs text-[var(--text-muted)]">{$t('filter_added_after')}</span>
        <input
          type="date"
          class="input"
          value={state.addedAfter ?? ''}
          onchange={(e) => updateFilters({ addedAfter: (e.currentTarget as HTMLInputElement).value || null, page: 1 })}
        />
      </label>
      <label class="flex flex-col gap-1">
        <span class="text-xs text-[var(--text-muted)]">{$t('filter_added_before')}</span>
        <input
          type="date"
          class="input"
          value={state.addedBefore ?? ''}
          onchange={(e) => updateFilters({ addedBefore: (e.currentTarget as HTMLInputElement).value || null, page: 1 })}
        />
      </label>
    </div>

    <div class="grid grid-cols-2 gap-2">
      <label class="flex flex-col gap-1">
        <span class="text-xs text-[var(--text-muted)]">{$t('sort_by')}</span>
        <select
          class="input"
          value={state.sort}
          onchange={(e) => updateFilters({ sort: (e.currentTarget as HTMLSelectElement).value, page: 1 })}
        >
          <option value="sort_title">{$t('sort_title')}</option>
          <option value="pubdate">{$t('sort_date')}</option>
          <option value="timestamp">{$t('sort_added')}</option>
          <option value="last_read">{$t('filter_sort_last_read')}</option>
          <option value="progress">{$t('filter_sort_progress')}</option>
        </select>
      </label>
      <label class="flex flex-col gap-1">
        <span class="text-xs text-[var(--text-muted)]">{$t('sort_by')}</span>
        <select
          class="input"
          value={state.order}
          onchange={(e) => updateFilters({ order: (e.currentTarget as HTMLSelectElement).value as 'asc' | 'desc', page: 1 })}
        >
          <option value="asc">{$t('filter_sort_asc')}</option>
          <option value="desc">{$t('filter_sort_desc')}</option>
        </select>
      </label>
    </div>
  </div>
</div>

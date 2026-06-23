<script lang="ts">
  import FilterChip from './FilterChip.svelte';
  import { t } from '$stores/i18n';
  import { updateFilters, clearFilters, activeFilterCount, type LibraryFiltersState } from '$stores/libraryFilters';
  import type { FilterOptions, AuthorCount, TagCount, SeriesCount, NameCount } from '$api/types';

  interface Props {
    options: FilterOptions | null;
    state: LibraryFiltersState;
    mode: 'sidebar' | 'drawer';
  }
  let { options, state, mode }: Props = $props();

  function lookupName(list: { name: string; id?: number }[], key: string | number, byId: boolean): string {
    if (byId) {
      const item = list.find((x) => (x as { id?: number }).id === Number(key));
      return item ? (item as { name: string }).name : String(key);
    }
    const item = list.find((x) => x.name === String(key));
    return item ? item.name : String(key);
  }

  function toggleInArray(arr: number[] | string[], v: number | string): (number | string)[] {
    const has = arr.includes(v as never);
    if (has) return arr.filter((x) => x !== v);
    return [...arr, v];
  }

  function setAuthors(v: number[]) {
    updateFilters({ authors: v, page: 1 });
  }
  function setTags(v: number[]) {
    updateFilters({ tags: v, page: 1 });
  }
  function setSeries(v: number[]) {
    updateFilters({ series: v, page: 1 });
  }
  function setFormats(v: string[]) {
    updateFilters({ formats: v, page: 1 });
  }
  function setLanguages(v: string[]) {
    updateFilters({ languages: v, page: 1 });
  }

  const count = $derived(activeFilterCount(state));
</script>

<div
  class="{mode === 'drawer' ? 'flex flex-col gap-4' : 'flex flex-col gap-4'}"
>
  {#if count > 0}
    <div>
      <div class="text-xs text-[var(--text-muted)] mb-2">{$t('filter_active')}</div>
      <div class="flex flex-wrap gap-1.5">
        {#each state.authors as id (id)}
          <FilterChip
            label={$t('filter_author')}
            value={lookupName(options?.authors ?? [], id, true)}
            onRemove={() => setAuthors(state.authors.filter((a) => a !== id))}
          />
        {/each}
        {#each state.tags as id (id)}
          <FilterChip
            label={$t('filter_tag')}
            value={lookupName(options?.tags ?? [], id, true)}
            onRemove={() => setTags(state.tags.filter((a) => a !== id))}
          />
        {/each}
        {#each state.series as id (id)}
          <FilterChip
            label={$t('filter_series')}
            value={lookupName(options?.series ?? [], id, true)}
            onRemove={() => setSeries(state.series.filter((a) => a !== id))}
          />
        {/each}
        {#each state.formats as f (f)}
          <FilterChip
            label={$t('filter_format')}
            value={f}
            onRemove={() => setFormats(state.formats.filter((a) => a !== f))}
          />
        {/each}
        {#each state.languages as l (l)}
          <FilterChip
            label={$t('filter_language')}
            value={l}
            onRemove={() => setLanguages(state.languages.filter((a) => a !== l))}
          />
        {/each}
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
    <label class="flex flex-col gap-1">
      <span class="text-xs text-[var(--text-muted)]">{$t('filter_author')}</span>
      <select
        multiple
        size="4"
        class="input"
        title={$t('filter_multi_hint')}
        value={state.authors.map(String)}
        onchange={(e) => {
          const sel = e.currentTarget as HTMLSelectElement;
          setAuthors(Array.from(sel.selectedOptions).map((o) => parseInt(o.value, 10)));
        }}
      >
        {#each options?.authors ?? [] as opt (opt.id)}
          <option value={opt.id}>{opt.name} ({opt.count})</option>
        {/each}
      </select>
      <span class="text-[0.65rem] text-[var(--text-muted)]">
        {$t('filter_multi_hint')}
      </span>
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-xs text-[var(--text-muted)]">{$t('filter_tag')}</span>
      <select
        multiple
        size="4"
        class="input"
        title={$t('filter_multi_hint')}
        value={state.tags.map(String)}
        onchange={(e) => {
          const sel = e.currentTarget as HTMLSelectElement;
          setTags(Array.from(sel.selectedOptions).map((o) => parseInt(o.value, 10)));
        }}
      >
        {#each options?.tags ?? [] as opt (opt.id)}
          <option value={opt.id}>{opt.name} ({opt.count})</option>
        {/each}
      </select>
      <span class="text-[0.65rem] text-[var(--text-muted)]">
        {$t('filter_multi_hint')}
      </span>
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-xs text-[var(--text-muted)]">{$t('filter_series')}</span>
      <select
        multiple
        size="3"
        class="input"
        title={$t('filter_multi_hint')}
        value={state.series.map(String)}
        onchange={(e) => {
          const sel = e.currentTarget as HTMLSelectElement;
          setSeries(Array.from(sel.selectedOptions).map((o) => parseInt(o.value, 10)));
        }}
      >
        {#each options?.series ?? [] as opt (opt.id)}
          <option value={opt.id}>{opt.name} ({opt.count})</option>
        {/each}
      </select>
      <span class="text-[0.65rem] text-[var(--text-muted)]">
        {$t('filter_multi_hint')}
      </span>
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-xs text-[var(--text-muted)]">{$t('filter_format')}</span>
      <select
        multiple
        size="3"
        class="input"
        title={$t('filter_multi_hint')}
        value={state.formats}
        onchange={(e) => {
          const sel = e.currentTarget as HTMLSelectElement;
          setFormats(Array.from(sel.selectedOptions).map((o) => o.value));
        }}
      >
        {#each options?.formats ?? [] as opt (opt.name)}
          <option value={opt.name}>{opt.name} ({opt.count})</option>
        {/each}
      </select>
      <span class="text-[0.65rem] text-[var(--text-muted)]">
        {$t('filter_multi_hint')}
      </span>
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-xs text-[var(--text-muted)]">{$t('filter_language')}</span>
      <select
        multiple
        size="3"
        class="input"
        title={$t('filter_multi_hint')}
        value={state.languages}
        onchange={(e) => {
          const sel = e.currentTarget as HTMLSelectElement;
          setLanguages(Array.from(sel.selectedOptions).map((o) => o.value));
        }}
      >
        {#each options?.languages ?? [] as opt (opt.name)}
          <option value={opt.name}>{opt.name} ({opt.count})</option>
        {/each}
      </select>
      <span class="text-[0.65rem] text-[var(--text-muted)]">
        {$t('filter_multi_hint')}
      </span>
    </label>

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

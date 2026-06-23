<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { books as booksApi, library as libraryApi } from '$api/client';
  import BookGrid from '$components/BookGrid.svelte';
  import FilterBar from '$components/library/FilterBar.svelte';
  import FilterDrawer from '$components/library/FilterDrawer.svelte';
  import MultiSelectBar from '$components/library/MultiSelectBar.svelte';
  import { t } from '$stores/i18n';
  import { toast } from '$stores/toast';
  import type { BookSummary, FilterOptions } from '$api/types';
  import {
    libraryFilters,
    initLibraryFiltersBinding,
    activeFilterCount,
    updateFilters,
  } from '$stores/libraryFilters';
  import {
    initLibrarySelectionBinding,
    selectedCount,
    setSelectedAll,
  } from '$stores/librarySelection';

  let items = $state<BookSummary[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let filterOptions = $state<FilterOptions | null>(null);
  let drawerOpen = $state(false);

  const pageSize = 24;
  const selectMode = $derived($selectedCount > 0);
  let searchInput = $state('');

  let fileInput = $state<HTMLInputElement>();
  let uploading = $state(false);

  function triggerUpload() {
    fileInput?.click();
  }

  async function handleFileChange(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    uploading = true;
    toast.info($t('uploading'));
    try {
      await booksApi.upload(file);
      toast.success($t('book_upload_success'));
      await load();
    } catch (err: any) {
      toast.error(err.detail || $t('book_upload_error'));
    } finally {
      uploading = false;
      input.value = '';
    }
  }

  async function load() {
    loading = true;
    try {
      const s = $libraryFilters;
      const params = {
        page: s.page,
        page_size: pageSize,
        search: s.search || undefined,
        author: s.authors[0],
        tag: s.tags[0],
        series: s.series[0],
        format: s.formats[0],
        language: s.languages[0],
        added_after: s.addedAfter || undefined,
        added_before: s.addedBefore || undefined,
        sort: s.sort,
        order: s.order,
      };
      const res = await booksApi.list(params);
      items = res.items;
      total = res.total;
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail ?? 'error';
      toast.error(detail);
    } finally {
      loading = false;
    }
  }

  // Reload when filters change
  $effect(() => {
    // Touch each piece of state that should trigger a reload
    const s = $libraryFilters;
    void [s.page, s.sort, s.order, s.search, s.addedAfter, s.addedBefore,
          s.authors.length, s.tags.length, s.series.length, s.formats.length, s.languages.length];
    load();
  });

  onMount(() => {
    initLibraryFiltersBinding();
    initLibrarySelectionBinding();
    // Load filter options once.
    libraryApi.filters().then((opts) => {
      filterOptions = opts;
    }).catch((err: unknown) => {
      const e = err as { detail?: string; message?: string };
      toast.error(e?.detail ?? e?.message ?? 'Failed to load filters');
    });
  });

  function setSearch(e: SubmitEvent) {
    e.preventDefault();
    updateFilters({ search: searchInput.trim(), page: 1 });
  }

  function changePage(p: number) {
    updateFilters({ page: p });
  }

  function selectAll() {
    setSelectedAll(items.map((b) => b.id));
  }

  function toggleSelectAll() {
    if ($selectedCount === items.length) {
      setSelectedAll([]);
    } else {
      selectAll();
    }
  }

  const totalPages = $derived(Math.ceil(total / pageSize));
  const filterCount = $derived(activeFilterCount($libraryFilters));
</script>

<svelte:head>
  <title>{$t('library')} — Alejandría</title>
</svelte:head>

<div class="p-6 md:p-8 max-w-7xl mx-auto">
  <header class="mb-6 flex flex-col md:flex-row md:items-center gap-3">
    <h1 class="font-serif text-2xl md:text-3xl flex-1">
      {$t('library')}
      <span class="text-base font-normal text-[var(--text-muted)]">({total.toLocaleString()})</span>
    </h1>
    <div class="flex flex-wrap items-center gap-2">
      <form onsubmit={setSearch} class="flex gap-2">
        <input
          type="search"
          bind:value={searchInput}
          placeholder={$t('search_placeholder')}
          class="input md:w-64"
        />
        <button type="submit" class="btn btn-primary">{$t('search_btn')}</button>
      </form>
      <!-- Mobile filter button -->
      <button
        type="button"
        class="btn btn-secondary lg:hidden relative"
        onclick={() => (drawerOpen = true)}
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
        </svg>
        {$t('filter_open_drawer')}
        {#if filterCount > 0}
          <span class="ml-1 inline-flex items-center justify-center w-5 h-5 text-xs rounded-full" style="background: var(--accent); color: var(--accent-text);">
            {filterCount}
          </span>
        {/if}
      </button>
      <button class="btn btn-secondary flex items-center gap-1.5" onclick={triggerUpload} disabled={uploading}>
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        {uploading ? $t('uploading') : $t('upload_book')}
      </button>
      <input
        type="file"
        accept=".epub,.pdf,.mobi,.azw3,.azw,.fb2,.djvu,.rtf,.docx,.txt"
        class="hidden"
        bind:this={fileInput}
        onchange={handleFileChange}
      />
    </div>
  </header>

  <div class="grid grid-cols-1 lg:grid-cols-[16rem_1fr] gap-6">
    <!-- Sidebar (desktop) -->
    <aside class="hidden lg:block">
      <div class="sticky top-4">
        <FilterBar options={filterOptions} state={$libraryFilters} mode="sidebar" />
      </div>
    </aside>

    <!-- Main content -->
    <div>
      {#if $selectedCount > 0}
        <div class="mb-3 flex items-center gap-2 text-sm">
          <button type="button" class="underline hover:text-[var(--accent)]" onclick={toggleSelectAll}>
            {items.length > 0 && $selectedCount === items.length ? $t('deselect_all') : $t('select_all')}
          </button>
          <span class="text-[var(--text-muted)]">
            {$t('selected_count', { n: $selectedCount })}
          </span>
        </div>
      {/if}

      <BookGrid books={items} {loading} selectable={selectMode} />

      {#if total > pageSize}
        <nav class="flex items-center justify-center gap-2 mt-8">
          <button
            class="btn btn-secondary"
            disabled={$libraryFilters.page <= 1}
            onclick={() => changePage($libraryFilters.page - 1)}
          >{$t('prev_page')}</button>
          <span class="text-sm text-[var(--text-muted)]">
            {$t('page_of', { page: $libraryFilters.page, pages: totalPages })}
          </span>
          <button
            class="btn btn-secondary"
            disabled={$libraryFilters.page * pageSize >= total}
            onclick={() => changePage($libraryFilters.page + 1)}
          >{$t('next_page')}</button>
        </nav>
      {/if}
    </div>
  </div>
</div>

<FilterDrawer
  open={drawerOpen}
  options={filterOptions}
  state={$libraryFilters}
  resultCount={total}
  onClose={() => (drawerOpen = false)}
/>

<MultiSelectBar onChange={load} />

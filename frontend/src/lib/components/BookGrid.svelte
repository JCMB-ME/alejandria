<script lang="ts">
  import type { BookSummary } from '$api/types';
  import Cover from './Cover.svelte';
  import SelectableBookCard from './library/SelectableBookCard.svelte';
  import { t } from '$stores/i18n';
  import { libraryFilters, clearFilters } from '$stores/libraryFilters';
  import { activeFilterCount } from '$stores/libraryFilters';

  interface Props {
    books: BookSummary[];
    loading?: boolean;
    selectable?: boolean;
  }
  let { books, loading = false, selectable = false }: Props = $props();

  const filterCount = $derived(activeFilterCount($libraryFilters));
</script>

{#if loading}
  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
    {#each Array(12) as _}
      <div class="animate-pulse">
        <div class="aspect-[2/3] rounded-lg bg-[var(--surface)]"></div>
        <div class="h-3 mt-2 rounded bg-[var(--surface)]"></div>
        <div class="h-3 mt-1 w-2/3 rounded bg-[var(--surface)]"></div>
      </div>
    {/each}
  </div>
{:else if books.length === 0}
  <div class="text-center py-12 text-[var(--text-muted)]">
    {#if filterCount > 0}
      <p class="mb-2">{$t('no_books_match_filters')}</p>
      <p class="text-xs mb-4">{$t('active_filters_count', { n: filterCount })}</p>
      <button
        type="button"
        class="btn btn-secondary"
        onclick={() => clearFilters()}
      >
        {$t('filter_clear_all')}
      </button>
    {:else}
      <p>{$t('no_books_found')}</p>
    {/if}
  </div>
{:else}
  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
    {#each books as book (book.id)}
      {#if selectable}
        <SelectableBookCard {book} />
      {:else}
        <a href="/books/{book.id}" class="group block">
          <div class="aspect-[2/3] overflow-hidden rounded-lg shadow-soft group-hover:shadow-elevated transition-shadow" style="background: var(--surface);">
            <Cover {book} size="medium" class="w-full h-full object-cover" />
          </div>
          <div class="mt-2">
            <h3 class="text-sm font-medium leading-tight line-clamp-2 group-hover:text-[var(--accent)]">
              {book.title}
            </h3>
            {#if book.authors.length}
              <p class="text-xs text-[var(--text-muted)] mt-0.5 line-clamp-1">
                {book.authors.map((a) => a.name).join(', ')}
              </p>
            {/if}
          </div>
        </a>
      {/if}
    {/each}
  </div>
{/if}

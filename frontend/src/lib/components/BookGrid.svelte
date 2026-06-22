<script lang="ts">
  import type { BookSummary } from '$api/types';
  import Cover from './Cover.svelte';
  import { t } from '$stores/i18n';

  interface Props {
    books: BookSummary[];
    loading?: boolean;
  }
  let { books, loading = false }: Props = $props();
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
    <p>{$t('no_books_found')}</p>
  </div>
{:else}
  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
    {#each books as book (book.id)}
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
    {/each}
  </div>
{/if}

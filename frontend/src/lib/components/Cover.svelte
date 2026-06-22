<script lang="ts">
  import type { BookSummary } from '$api/types';
  import { t } from '$stores/i18n';

  interface Props {
    book: Pick<BookSummary, 'id' | 'title' | 'authors' | 'has_cover' | 'cover_path'>;
    size?: 'thumb' | 'small' | 'medium' | 'large';
    class?: string;
  }
  let { book, size = 'medium', class: className = '' }: Props = $props();

  let errored = $state(false);
  let coverUrl = $derived(`/api/library/covers/${book.id}.jpg?size=${size}&t=${(book as any).last_modified || ''}`);
</script>

{#if !errored && book.has_cover}
  <img
    src={coverUrl}
    alt={book.title}
    loading="lazy"
    class={className}
    onerror={() => (errored = true)}
  />
{:else}
  <!-- Placeholder cover with title -->
  <div
    class="flex flex-col justify-between p-3 {className}"
    style="background: linear-gradient(135deg, var(--surface), color-mix(in srgb, var(--surface) 70%, var(--accent) 30%)); aspect-ratio: 2/3;"
  >
    <div class="text-[10px] uppercase tracking-wider opacity-60">{$t('book')} #{book.id}</div>
    <div>
      <div class="font-serif text-sm font-semibold leading-tight line-clamp-4" style="color: var(--text);">
        {book.title}
      </div>
      {#if book.authors.length}
        <div class="text-xs mt-1 opacity-70 line-clamp-1">{book.authors[0].name}</div>
      {/if}
    </div>
  </div>
{/if}

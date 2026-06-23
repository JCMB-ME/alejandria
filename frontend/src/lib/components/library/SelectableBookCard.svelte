<script lang="ts">
  import type { BookSummary } from '$api/types';
  import Cover from '../Cover.svelte';
  import { librarySelection, toggleSelected, isSelected } from '$stores/librarySelection';
  import { goto } from '$app/navigation';

  interface Props {
    book: BookSummary;
  }
  let { book }: Props = $props();

  // Svelte 5 reactive read from the store
  let selected = $derived(($librarySelection as Set<number>).has(book.id));
</script>

<div class="relative group">
  <!-- Checkbox overlay -->
  <label
    class="absolute top-2 left-2 z-10 inline-flex items-center justify-center w-7 h-7 rounded cursor-pointer transition-opacity {selected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100'}"
    style="background: color-mix(in srgb, var(--surface) 80%, transparent);"
  >
    <input
      type="checkbox"
      class="w-4 h-4 accent-[var(--accent)] cursor-pointer"
      checked={selected}
      onchange={(e) => {
        e.stopPropagation();
        toggleSelected(book.id);
      }}
      onclick={(e) => e.stopPropagation()}
    />
  </label>

  {#if selected}
    <div
      class="absolute inset-0 rounded-lg ring-2 ring-[var(--accent)] pointer-events-none z-[5]"
      aria-hidden="true"
    ></div>
  {/if}

  <button
    type="button"
    class="block w-full text-left"
    onclick={() => goto(`/books/${book.id}`)}
  >
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
  </button>
</div>

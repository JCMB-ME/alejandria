<script lang="ts">
  import { onMount } from 'svelte';
  import { shelves } from '$api/client';
  import type { Shelf } from '$api/types';
  import { t } from '$stores/i18n';
  import { goto } from '$app/navigation';

  interface Props {
    mode: 'add' | 'remove';
    onClose: () => void;
    onPick: (shelf: Shelf) => void;
  }
  let { mode, onClose, onPick }: Props = $props();

  let list = $state<Shelf[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      list = await shelves.list();
    } catch (err: unknown) {
      error = (err as { detail?: string })?.detail ?? 'error';
    } finally {
      loading = false;
    }
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onClose();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
  role="dialog"
  aria-modal="true"
  aria-labelledby="shelf-picker-title"
  tabindex="-1"
  onclick={(e) => { if (e.target === e.currentTarget) onClose(); }}
  onkeydown={handleKeydown}
>
  <div
    class="w-full max-w-md rounded-xl shadow-2xl border overflow-hidden"
    style="background: var(--surface); border-color: var(--border);"
  >
    <div class="px-6 py-4 flex items-center justify-between border-b" style="border-color: var(--border);">
      <h2 id="shelf-picker-title" class="text-lg font-semibold">
        {$t('bulk_choose_shelf')}
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

    <div class="max-h-80 overflow-y-auto p-2">
      {#if loading}
        <div class="p-6 text-center text-sm text-[var(--text-muted)]">{$t('loading')}</div>
      {:else if error}
        <div class="p-6 text-center text-sm text-[var(--danger)]">{error}</div>
      {:else if list.length === 0}
        <div class="p-6 text-center text-sm text-[var(--text-muted)] space-y-3">
          <p>{$t('bulk_no_shelves')}</p>
          <button
            type="button"
            class="btn btn-primary"
            onclick={() => { onClose(); goto('/shelves'); }}
          >{$t('shelves')}</button>
        </div>
      {:else}
        <ul class="flex flex-col">
          {#each list as shelf (shelf.id)}
            <li>
              <button
                type="button"
                class="w-full text-left px-3 py-2 rounded hover:bg-[var(--surface-hover)] flex items-center gap-2"
                onclick={() => onPick(shelf)}
              >
                {#if shelf.color}
                  <span class="inline-block w-3 h-3 rounded-full" style="background: {shelf.color};"></span>
                {/if}
                <span class="flex-1">{shelf.name}</span>
                <span class="text-xs text-[var(--text-muted)]">{shelf.book_count}</span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="px-6 py-3 border-t flex justify-end" style="border-color: var(--border);">
      <button type="button" class="btn btn-ghost" onclick={onClose}>
        {$t('bulk_cancel')}
      </button>
    </div>
  </div>
</div>

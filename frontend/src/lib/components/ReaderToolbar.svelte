<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { BookDetail } from '$api/types';
  import { readerTheme } from '$stores/auth';
  import { t } from '$stores/i18n';

  interface Props {
    book: BookDetail | null;
    progressPct: number;
    currentPage: number;
    totalPages: number;
    fontSize: number;
    fontFamily: 'serif' | 'sans';
    lineHeight: number;
    toc: { id: string; label: string; href?: string }[];
    showToc: boolean;
    showHighlights: boolean;
    highlights: any[];
  }
  let {
    book, progressPct, currentPage, totalPages, fontSize, fontFamily, lineHeight,
    toc, showToc, showHighlights, highlights
  }: Props = $props();

  const dispatch = createEventDispatcher();
</script>

<header class="h-14 border-b flex items-center px-3 gap-2 shrink-0" style="background: var(--surface); border-color: var(--border);">
  <button class="btn btn-ghost !p-2" onclick={() => dispatch('close')} title={$t('back_to_book')}>
    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
  </button>

  <div class="flex-1 min-w-0 text-center">
    <div class="text-sm font-medium truncate">{book?.title || $t('reading_loading')}</div>
    <div class="text-xs text-[var(--text-soft)] flex items-center justify-center gap-2">
      <button class="hover:text-[var(--text)]" onclick={() => dispatch('prev')}>‹ {$t('prev')}</button>
      <span>{currentPage} / {totalPages}</span>
      <button class="hover:text-[var(--text)]" onclick={() => dispatch('next')}>{$t('next')} ›</button>
      <span>· {Math.round((progressPct || 0) * 100)}%</span>
    </div>
  </div>

  <button class="btn btn-ghost !p-2" class:active={showToc} onclick={() => dispatch('toggleToc')} title={$t('toc')}>
    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
  </button>

  <div class="flex items-center gap-0.5">
    <button class="btn btn-ghost !p-2" onclick={() => dispatch('fontSize', -2)} title={$t('smaller_text')}>A-</button>
    <span class="text-xs w-7 text-center">{fontSize}</span>
    <button class="btn btn-ghost !p-2" onclick={() => dispatch('fontSize', 2)} title={$t('larger_text')}>A+</button>
  </div>

  <button class="btn btn-ghost !p-2" onclick={() => dispatch('fontFamily', fontFamily === 'serif' ? 'sans' : 'serif')} title={$t('font_family')}>
    <span class="font-serif text-sm">Aa</span>
  </button>

  <div class="flex items-center gap-0.5">
    {#each ['light', 'sepia', 'dark'] as tVal}
      <button
        class="btn btn-ghost !p-2"
        class:active={$readerTheme === tVal}
        onclick={() => dispatch('theme', tVal)}
        title={tVal}
      >
        {#if tVal === 'light'}
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/></svg>
        {:else if tVal === 'sepia'}
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
        {:else}
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        {/if}
      </button>
    {/each}
  </div>

  <button class="btn btn-ghost !p-2" class:active={showHighlights} onclick={() => dispatch('toggleHighlights')} title={$t('highlights')}>
    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
  </button>

  {#if highlights.length}
    <span class="badge text-xs">{highlights.length}</span>
  {/if}

  <button class="btn btn-ghost !p-2" onclick={() => dispatch('saveHighlight', 'yellow')} title={$t('highlight_selection')}>
    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M9 11l-6 6 1 4 4-1 6-6m-5-5l4 4 7-7-4-4-7 7z"/></svg>
  </button>
</header>

{#if showToc}
  <aside class="absolute right-0 top-14 bottom-0 w-72 border-l p-4 overflow-y-auto z-10" style="background: var(--surface); border-color: var(--border);">
    <h3 class="font-semibold mb-3 text-sm">{$t('toc')}</h3>
    <ol class="space-y-1 text-sm">
      {#each toc as item}
        <li>
          <a href={item.href || '#'} class="block py-1 px-2 rounded hover:bg-[var(--elevated)]">{item.label}</a>
        </li>
      {:else}
        <li class="text-[var(--text-muted)] text-xs">{$t('no_toc')}</li>
      {/each}
    </ol>
  </aside>
{/if}

{#if showHighlights}
  <aside class="absolute right-0 top-14 bottom-0 w-80 border-l p-4 overflow-y-auto z-10" style="background: var(--surface); border-color: var(--border);">
    <h3 class="font-semibold mb-3 text-sm">{$t('highlights')} ({highlights.length})</h3>
    <div class="space-y-3 text-sm">
      {#each highlights as h}
        <blockquote class="border-l-2 pl-2 italic" style="border-color: var(--accent);">
          {h.text}
        </blockquote>
      {:else}
        <p class="text-[var(--text-muted)] text-xs">{$t('select_text_to_highlight')}</p>
      {/each}
    </div>
  </aside>
{/if}

<style>
  .active {
    background: var(--elevated);
  }
</style>

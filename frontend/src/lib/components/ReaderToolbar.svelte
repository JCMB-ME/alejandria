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
    /**
     * CFI range of the user's current text selection in the reader, or
     * empty string when nothing is selected. The save-highlight button
     * uses this to disable itself when there's nothing to save — the
     * previous always-enabled button was misleading on mobile because
     * tapping it with no selection silently no-op'd.
     */
    selectedCfi: string;
  }
  let {
    book, progressPct, currentPage, totalPages, fontSize, fontFamily, lineHeight,
    toc, showToc, showHighlights, highlights, selectedCfi
  }: Props = $props();

  const dispatch = createEventDispatcher();

  // Drawer chrome on the right. We use 85vw on phones (so the page edge
  // is still visible behind) and clamp to 320px on larger screens. The
  // mobile TOC trigger is in row 1 of the toolbar so the user can open
  // chapters without scrolling the controls bar first.
  const themeButtons = ['light', 'sepia', 'dark'] as const;
</script>

<header class="border-b shrink-0" style="background: var(--surface); border-color: var(--border);">
  <!--
    Row 1: always visible, always 56px tall. Holds the back button,
    the title + page indicator, and (on mobile only) the two drawer
    triggers. On `md:` and up the TOC and Highlights buttons live in
    row 2 because row 2 is hidden there, so they need to be reachable
    from row 1 too — but on desktop we leave row 1 minimal and let
    row 2 carry the controls.
  -->
  <div class="h-14 flex items-center px-3 gap-2">
    <button class="btn btn-ghost !p-2 touch-target" onclick={() => dispatch('close')} title={$t('back_to_book')} aria-label={$t('back_to_book')}>
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
    </button>

    <div class="flex-1 min-w-0 text-center">
      <div class="text-sm font-medium truncate">{book?.title || $t('reading_loading')}</div>
      <div class="text-xs text-[var(--text-soft)] flex items-center justify-center gap-2 min-w-0 truncate">
        <button class="hover:text-[var(--text)] touch-target" onclick={() => dispatch('prev')} aria-label={$t('prev')}>‹ {$t('prev')}</button>
        <span class="whitespace-nowrap">{currentPage} / {totalPages}</span>
        <button class="hover:text-[var(--text)] touch-target" onclick={() => dispatch('next')} aria-label={$t('next')}>{$t('next')} ›</button>
        <span class="whitespace-nowrap">· {Math.round((progressPct || 0) * 100)}%</span>
      </div>
    </div>

    <!-- Mobile-only drawer triggers. On `md:` and up these are duplicated
         in row 2's controls bar, so we hide them here to avoid redundancy. -->
    <button
      class="btn btn-ghost !p-2 touch-target md:hidden"
      class:active={showToc}
      onclick={() => dispatch('toggleToc')}
      title={$t('toc')}
      aria-label={$t('toc')}
    >
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
    </button>
    <button
      class="btn btn-ghost !p-2 touch-target md:hidden"
      class:active={showHighlights}
      onclick={() => dispatch('toggleHighlights')}
      title={$t('highlights')}
      aria-label={$t('highlights')}
    >
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
    </button>
    {#if highlights.length}
      <span class="badge text-xs md:hidden">{highlights.length}</span>
    {/if}
  </div>

  <!--
    Row 2: mobile-only controls bar (h-12). Horizontally scrollable so
    it never breaks the layout — long chapter indicator strings won't
    push other controls off-screen. The order is: prev / page / next,
    then font size, then theme, then font family, then highlight.
    Desktop (md:) gets the original controls directly inside row 1 —
    see the version below.
  -->
  <div class="h-12 flex items-center px-3 gap-1 overflow-x-auto md:hidden border-t" style="border-color: var(--border);">
    <button class="btn btn-ghost !p-2 touch-target shrink-0" onclick={() => dispatch('fontSize', -2)} title={$t('smaller_text')} aria-label={$t('smaller_text')}>A-</button>
    <span class="text-xs w-9 text-center shrink-0">{fontSize}</span>
    <button class="btn btn-ghost !p-2 touch-target shrink-0" onclick={() => dispatch('fontSize', 2)} title={$t('larger_text')} aria-label={$t('larger_text')}>A+</button>

    <div class="w-px h-6 bg-[var(--border)] shrink-0"></div>

    {#each themeButtons as tVal}
      <button
        class="btn btn-ghost !p-2 touch-target shrink-0"
        class:active={$readerTheme === tVal}
        onclick={() => dispatch('theme', tVal)}
        title={tVal}
        aria-label={tVal}
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

    <div class="w-px h-6 bg-[var(--border)] shrink-0"></div>

    <button class="btn btn-ghost !p-2 touch-target shrink-0" onclick={() => dispatch('fontFamily', fontFamily === 'serif' ? 'sans' : 'serif')} title={$t('font_family')} aria-label={$t('font_family')}>
      <span class="font-serif text-sm">Aa</span>
    </button>

    <button
      class="btn btn-ghost !p-2 touch-target shrink-0"
      disabled={!selectedCfi}
      onclick={() => dispatch('saveHighlight', 'yellow')}
      title={$t('highlight_selection')}
      aria-label={$t('highlight_selection')}
    >
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M9 11l-6 6 1 4 4-1 6-6m-5-5l4 4 7-7-4-4-7 7z"/></svg>
    </button>
  </div>

  <!--
    Row 2 (desktop variant): the original single-row controls. Hidden on
    mobile, visible on md:+. We keep the same DOM that was here before
    so desktop UX is unchanged.
  -->
  <div class="hidden md:flex h-12 items-center px-3 gap-2 overflow-x-auto border-t" style="border-color: var(--border);">
    <button class="btn btn-ghost !p-2 touch-target shrink-0" onclick={() => dispatch('toggleToc')} title={$t('toc')} aria-label={$t('toc')}>
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
    </button>
    <div class="flex items-center gap-0.5 shrink-0">
      <button class="btn btn-ghost !p-2 touch-target" onclick={() => dispatch('fontSize', -2)} title={$t('smaller_text')} aria-label={$t('smaller_text')}>A-</button>
      <span class="text-xs w-7 text-center">{fontSize}</span>
      <button class="btn btn-ghost !p-2 touch-target" onclick={() => dispatch('fontSize', 2)} title={$t('larger_text')} aria-label={$t('larger_text')}>A+</button>
    </div>
    <button class="btn btn-ghost !p-2 touch-target shrink-0" onclick={() => dispatch('fontFamily', fontFamily === 'serif' ? 'sans' : 'serif')} title={$t('font_family')} aria-label={$t('font_family')}>
      <span class="font-serif text-sm">Aa</span>
    </button>
    <div class="flex items-center gap-0.5 shrink-0">
      {#each themeButtons as tVal}
        <button
          class="btn btn-ghost !p-2 touch-target"
          class:active={$readerTheme === tVal}
          onclick={() => dispatch('theme', tVal)}
          title={tVal}
          aria-label={tVal}
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
    <button class="btn btn-ghost !p-2 touch-target shrink-0" onclick={() => dispatch('toggleHighlights')} title={$t('highlights')} aria-label={$t('highlights')}>
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
    </button>
    {#if highlights.length}
      <span class="badge text-xs shrink-0">{highlights.length}</span>
    {/if}
    <button
      class="btn btn-ghost !p-2 touch-target shrink-0"
      disabled={!selectedCfi}
      onclick={() => dispatch('saveHighlight', 'yellow')}
      title={$t('highlight_selection')}
      aria-label={$t('highlight_selection')}
    >
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M9 11l-6 6 1 4 4-1 6-6m-5-5l4 4 7-7-4-4-7 7z"/></svg>
    </button>
  </div>
</header>

<!--
  Scrim — a transparent full-screen button that closes whichever drawer
  is open when the user taps outside. Hidden on md: because the desktop
  drawers are inline and don't need a scrim. z-[5] sits below the drawer
  (z-10) so taps on the drawer itself still hit drawer content.
-->
{#if showToc || showHighlights}
  <button
    class="fixed inset-0 bg-black/40 z-[5] md:hidden"
    aria-label="Close panel"
    onclick={() => {
      if (showToc) dispatch('toggleToc');
      if (showHighlights) dispatch('toggleHighlights');
    }}
  ></button>
{/if}

{#if showToc}
  <aside
    class="fixed right-0 top-14 md:top-[104px] bottom-0 w-[85vw] max-w-80 border-l p-4 overflow-y-auto z-10"
    style="background: var(--surface); border-color: var(--border);"
    role="dialog"
    aria-label={$t('toc')}
  >
    <div class="flex items-center justify-between mb-3 gap-2">
      <h3 class="font-semibold text-sm">{$t('toc')}</h3>
      <button class="btn btn-ghost !p-2 touch-target shrink-0" onclick={() => dispatch('toggleToc')} aria-label={$t('close')}>
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
    <ol class="space-y-1 text-sm">
      {#each toc as item}
        <li>
          <!--
            We render a button instead of an anchor because the href is
            an EPUB-internal fragment like "#ch1" — clicking an <a> would
            navigate the outer page instead of jumping inside the book.
          -->
          <button
            type="button"
            class="block w-full text-left py-2 px-2 rounded hover:bg-[var(--elevated)] touch-target"
            onclick={() => dispatch('jumpToToc', item.href)}
          >
            {item.label}
          </button>
        </li>
      {:else}
        <li class="text-[var(--text-muted)] text-xs">{$t('no_toc')}</li>
      {/each}
    </ol>
  </aside>
{/if}

{#if showHighlights}
  <aside
    class="fixed right-0 top-14 md:top-[104px] bottom-0 w-[85vw] max-w-80 border-l p-4 overflow-y-auto z-10"
    style="background: var(--surface); border-color: var(--border);"
    role="dialog"
    aria-label={$t('highlights')}
  >
    <div class="flex items-center justify-between mb-3 gap-2">
      <h3 class="font-semibold text-sm">{$t('highlights')} ({highlights.length})</h3>
      <button class="btn btn-ghost !p-2 touch-target shrink-0" onclick={() => dispatch('toggleHighlights')} aria-label={$t('close')}>
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
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
  /* Hide the horizontal scrollbar on the controls bar so it doesn't
     waste vertical space on mobile. Still scrollable via touch/drag. */
  .overflow-x-auto::-webkit-scrollbar {
    display: none;
  }
  .overflow-x-auto {
    scrollbar-width: none;
  }
</style>

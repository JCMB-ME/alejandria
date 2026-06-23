<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { page } from '$app/stores';
  import type { BookDetail, Highlight } from '$api/types';
  import { readerTheme } from '$stores/auth';
  import { t } from '$stores/i18n';
  import { toast } from '$stores/toast';
  import HighlightItem from './HighlightItem.svelte';

  interface Props {
    book: BookDetail | null;
    progressPct: number;
    currentPage: number;
    totalPages: number;
    /**
     * Feature 1: controlled value for the jump-to-page <input>. Parent
     * (+page.svelte) keeps this in sync with the current display page
     * via a $effect so prev/next/jump reflect into the field.
     */
    pageInputValue: number;
    pageInputTotal: number;
    /**
     * True while EPUB locations are still generating — disables the
     * jump input + button with a "…" placeholder. PDF/CBZ never
     * disable because their totals are known up front.
     */
    pageInputDisabled: boolean;
    fontSize: number;
    fontFamily: 'serif' | 'sans';
    lineHeight: number;
    toc: { id: string; label: string; href?: string }[];
    showToc: boolean;
    showHighlights: boolean;
    highlights: Highlight[];
    /**
     * CFI range of the user's current text selection in the reader, or
     * empty string when nothing is selected. The save-highlight button
     * uses this to disable itself when there's nothing to save — the
     * previous always-enabled button was misleading on mobile because
     * tapping it with no selection silently no-op'd.
     */
    selectedCfi: string;
    /**
     * Book format type — used by Feature 3c to decide whether to show
     * the `p. N` / `pág. N` page indicator next to each highlight.
     * EPUB doesn't show one because the virtual-page index isn't
     * wired into the highlight creation flow yet.
     */
    bookFormatType: 'epub' | 'pdf' | 'cbz' | 'fb2' | 'rtf' | 'txt' | null;
    /** Feature 1: jump to a user-typed page number. */
    onJumpToPage: (n: number) => void;
    /** Feature 2: delete a saved highlight by id. */
    onDeleteHighlight: (id: number) => void;
    /** Feature 3b: jump to a saved highlight's location. */
    onJumpToHighlight: (h: Highlight) => void;
  }
  let {
    book, progressPct, currentPage, totalPages,
    pageInputValue, pageInputTotal, pageInputDisabled,
    fontSize, fontFamily, lineHeight,
    toc, showToc, showHighlights, highlights, selectedCfi, bookFormatType,
    onJumpToPage, onDeleteHighlight, onJumpToHighlight,
  }: Props = $props();

  const dispatch = createEventDispatcher();

  // Plan 3 / H8: Export modal state. Hidden by default; toggled by the
  // export button in the highlights drawer header.
  let showExportModal = $state(false);

  // Drawer chrome on the right. We use 85vw on phones (so the page edge
  // is still visible behind) and clamp to 320px on larger screens. The
  // mobile TOC trigger is in row 1 of the toolbar so the user can open
  // chapters without scrolling the controls bar first.
  const themeButtons = ['light', 'sepia', 'dark'] as const;

  /**
   * Plan 3 / H8: download highlights as either a per-book markdown file
   * or a per-user zip. The endpoint at `/api/highlights/export` picks the
   * right shape based on whether `book_id` is present.
   */
  async function exportHighlights(mode: 'per_book' | 'all') {
    showExportModal = false;
    const url = mode === 'per_book'
      ? `/api/highlights/export?format=markdown&book_id=${$page.params.id}`
      : `/api/highlights/export?format=markdown`;
    try {
      const r = await fetch(url, { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`export failed: ${r.status}`);
      const blob = await r.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = mode === 'per_book'
        ? 'highlights.md'
        : `highlights-${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      toast.success($t('highlight_export_done'));
    } catch {
      toast.error('Export failed');
    }
  }
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
      <div class="text-xs text-[var(--text-soft)] flex items-center justify-center gap-1 min-w-0 overflow-x-auto whitespace-nowrap scrollbar-none">
        <button class="hover:text-[var(--text)] touch-target shrink-0" onclick={() => dispatch('prev')} aria-label={$t('prev')}>‹ {$t('prev')}</button>
        <span class="whitespace-nowrap shrink-0">{currentPage} / {totalPages}</span>
        <button class="hover:text-[var(--text)] touch-target shrink-0" onclick={() => dispatch('next')} aria-label={$t('next')}>{$t('next')} ›</button>
        <!--
          Feature 1: jump-to-page input + button. Sits between `› next`
          and the progress percentage so the visual order is
          [‹ prev] [100] / [200] [Ir] [next ›] · 42%. The input is
          controlled by the parent (`pageInputValue`) and disabled while
          EPUB locations are still generating (`pageInputDisabled`).
          The `min`/`max` are browser-side hints — the parent clamps
          defensively in goToPage() anyway. The whole input+button
          group is wrapped in its own flex with shrink-0 so it stays
          reachable (via horizontal scroll on narrow viewports) instead
          of being truncated off-screen by the `min-w-0` on the parent.
        -->
        <div class="flex items-center gap-1 shrink-0">
          <input
            type="number"
            min="1"
            max={pageInputTotal}
            value={pageInputValue}
            disabled={pageInputDisabled}
            placeholder={pageInputDisabled ? '…' : String(pageInputValue || 1)}
            aria-label={$t('jump_to_page')}
            onkeydown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                onJumpToPage?.(pageInputValue);
              }
            }}
            oninput={(e) => {
              const v = parseInt((e.currentTarget as HTMLInputElement).value, 10);
              if (!Number.isNaN(v)) pageInputValue = v;
            }}
            class="w-10 text-center text-xs bg-transparent border rounded px-1 py-0.5"
          />
          <span>/</span>
          <span>{pageInputTotal}</span>
          <button
            class="btn btn-ghost !p-2 touch-target"
            disabled={pageInputDisabled}
            onclick={() => onJumpToPage?.(pageInputValue)}
            aria-label={$t('jump_btn')}
            title={$t('jump_btn')}
          >{$t('jump_btn')}</button>
        </div>
        <span class="whitespace-nowrap shrink-0">· {Math.round((progressPct || 0) * 100)}%</span>
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
      <div class="flex items-center gap-1">
        {#if highlights.length}
          <!--
            Plan 3 / H8: Export button. Hidden until there's at least
            one highlight (no point exporting an empty list).
          -->
          <button
            type="button"
            class="btn btn-ghost !p-1.5 touch-target shrink-0"
            title={$t('highlight_export_btn')}
            aria-label={$t('highlight_export_btn')}
            onclick={() => (showExportModal = true)}
          >
            <svg class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
          </button>
        {/if}
        <button class="btn btn-ghost !p-2 touch-target shrink-0" onclick={() => dispatch('toggleHighlights')} aria-label={$t('close')}>
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    </div>
    <div class="space-y-3 text-sm">
      {#each highlights as h (h.id)}
        <!--
          Plan 3 / H4 + H5: each highlight is now a <HighlightItem>
          component so the note input + color picker state stays local
          to each row. The parent keeps ownership of the highlights
          array and is updated by the save / color callbacks below.
        -->
        <HighlightItem
          highlight={h}
          {bookFormatType}
          onJump={(item) => onJumpToHighlight?.(item)}
          onDelete={(id) => onDeleteHighlight?.(id)}
        />
      {:else}
        <p class="text-[var(--text-muted)] text-xs">{$t('select_text_to_highlight')}</p>
      {/each}
    </div>
    <!--
      Plan 3 / H8: Export modal. Two buttons: per-book markdown or
      zip of every highlighted book. Closes on scrim tap via the
      `e.target === e.currentTarget` guard.
    -->
    {#if showExportModal}
      <div
        class="fixed inset-0 z-20 flex items-center justify-center p-4"
        style="background: rgba(0,0,0,0.5);"
        role="dialog"
        aria-modal="true"
        aria-label={$t('highlight_export_btn')}
        onclick={(e) => { if (e.target === e.currentTarget) showExportModal = false; }}
      >
        <div
          class="card max-w-sm w-full p-4"
          style="background: var(--surface);"
        >
          <h3 class="font-semibold text-sm mb-3">{$t('highlight_export_btn')}</h3>
          <div class="flex flex-col gap-2">
            <button
              class="btn btn-secondary w-full"
              onclick={() => exportHighlights('per_book')}
            >
              {$t('highlight_export_per_book')}
            </button>
            <button
              class="btn btn-secondary w-full"
              onclick={() => exportHighlights('all')}
            >
              {$t('highlight_export_all')}
            </button>
            <button
              class="btn btn-ghost w-full"
              onclick={() => (showExportModal = false)}
            >
              {$t('cancel_btn')}
            </button>
          </div>
        </div>
      </div>
    {/if}
  </aside>
{/if}

<style>
  .active {
    background: var(--elevated);
  }
  /* Hide the horizontal scrollbar on the controls bar so it doesn't
     waste vertical space on mobile. Still scrollable via touch/drag.
     `.scrollbar-none` covers row 1 (page indicator / jump input) while
     `.overflow-x-auto` covers the explicit mobile/desktop controls rows. */
  .overflow-x-auto::-webkit-scrollbar,
  .scrollbar-none::-webkit-scrollbar {
    display: none;
  }
  .overflow-x-auto,
  .scrollbar-none {
    scrollbar-width: none;
  }
</style>

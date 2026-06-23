<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { page } from '$app/stores';
  import { books as booksApi, reader as readerApi, highlights as highlightsApi } from '$api/client';
  import { readerTheme, setReaderTheme } from '$stores/auth';
  import type { BookDetail, ProgressRead, Highlight } from '$api/types';
  import { goto } from '$app/navigation';
  import ReaderToolbar from '$components/ReaderToolbar.svelte';
  import { t } from '$stores/i18n';
  import { toast } from '$stores/toast';
  import { confirm } from '$stores/confirm';
  import type { ReaderController, BookFormatType } from '$reader/types';
  import { createControllerFor } from '$reader/factory';

  let book = $state<BookDetail | null>(null);
  let progress = $state<ProgressRead | null>(null);
  let container: HTMLDivElement = $state() as HTMLDivElement;
  let bookElement: HTMLElement = $state() as HTMLElement;
  let controller: ReaderController | null = $state<ReaderController | null>(null);
  let unsubs: (() => void)[] = [];

  let toc = $state<{ id: string; label: string; href?: string }[]>([]);
  let showToc = $state(false);
  let showHighlights = $state(false);
  let highlights = $state<Highlight[]>([]);
  let selectedText = $state('');
  let selectedCfi = $state('');

  // Reader preferences.
  let fontSizeRem = $state(1.125);
  let fontFamily = $state<'serif' | 'sans'>('serif');
  let lineHeight = $state(1.7);

  // Sentinel-driven jump-input sync.
  let lastNavigatedPage = $state(0);
  let pageInputValue = $state(1);

  const id = $derived(parseInt($page.params.id || '0'));

  // Format detection at the page level (D8).
  const bookFormat = $derived.by(() => {
    if (!book) return null;
    const formats = book.formats.map((f) => f.fmt.toUpperCase());
    if (formats.includes('EPUB')) return { type: 'epub' as BookFormatType, url: `/api/reader/${id}/file/book.epub?fmt=EPUB` };
    if (formats.includes('PDF'))  return { type: 'pdf'  as BookFormatType, url: `/api/reader/${id}/file?fmt=PDF` };
    if (formats.includes('CBZ'))  return { type: 'cbz'  as BookFormatType, url: `/api/reader/${id}/file?fmt=CBZ` };
    if (formats.includes('CBR'))  return { type: 'cbz'  as BookFormatType, url: `/api/reader/${id}/file?fmt=CBR` };
    if (formats.includes('FB2'))  return { type: 'fb2'  as BookFormatType, url: `/api/reader/${id}/file/book.epub?fmt=FB2` };
    if (formats.includes('RTF'))  return { type: 'rtf'  as BookFormatType, url: `/api/reader/${id}/file/book.epub?fmt=RTF` };
    if (formats.includes('TXT'))  return { type: 'txt'  as BookFormatType, url: `/api/reader/${id}/file/book.epub?fmt=TXT` };
    return { type: 'epub' as BookFormatType, url: `/api/reader/${id}/file/book.epub` };
  });

  // Display values come from the controller's reactive state (D1).
  const displayPage = $derived(controller ? controller.currentPage : 0);
  const displayTotal = $derived(controller ? controller.totalPages : 0);
  const progressPct = $derived(controller ? controller.currentProgress : 0);
  const pageInputDisabled = $derived(!controller || !controller.canGoToPage);

  onMount(async () => {
    try {
      [book, progress] = await Promise.all([
        booksApi.get(id),
        readerApi.progress(id).catch(() => null),
      ]);
    } catch (e) {
      console.error('read_page_load_error', e);
      return;
    }

    await tick();
    if (!bookElement || !bookFormat) {
      console.error('read_page_no_book_element');
      return;
    }

    // Fetch saved highlights BEFORE the controller so it can render them.
    let savedHighlights: Highlight[] = [];
    try {
      savedHighlights = await highlightsApi.list(id);
      highlights = savedHighlights;
    } catch (e) {
      console.error('highlights_load_failed', e);
    }

    // Pick the per-format controller.
    const c = createControllerFor(bookFormat.type);
    controller = c;

    // Wire up events. Every callback is a thin delegate to the
    // controller or to the relevant API.
    unsubs.push(c.on('pagechange', () => { lastNavigatedPage++; }));
    unsubs.push(c.on('progress', (data) => {
      if (book) {
        readerApi.updateProgress({
          book_id: book.id,
          position: data.position,
          position_type: data.position_type,
          progress_pct: data.progress_pct,
        }).catch(() => {});
      }
    }));
    unsubs.push(c.on('selection', (data) => {
      selectedText = data.text;
      selectedCfi = data.cfi;
    }));
    unsubs.push(c.on('error', (data) => {
      console.error('reader_error', data);
      toast.error($t('jump_locations_failed') ?? data.message);
    }));
    unsubs.push(c.on('toc', (data) => {
      toc = data.items ?? [];
    }));
    unsubs.push(c.on('ready', () => { /* reactive getters fire */ }));
    unsubs.push(c.on('destroy', () => { /* no-op */ }));
    unsubs.push(c.on('highlight', () => { /* no-op */ }));

    try {
      await c.init(bookElement, bookFormat.url, {
        savedProgress: progress ? { position: progress.position, position_type: progress.position_type as any } : null,
        savedHighlights,
        readerTheme: $readerTheme,
        initialFontSizeRem: fontSizeRem,
        initialFontFamily: fontFamily,
        initialLineHeight: lineHeight,
        containerWidth: container?.clientWidth,
      });
    } catch (e) {
      console.error('read_page_init_failed', e);
    }
  });

  onDestroy(() => {
    for (const u of unsubs) try { u(); } catch {}
    controller?.destroy();
    controller = null;
  });

  // Toolbar callbacks — each is a thin delegate.
  const onPrev = () => controller?.prev();
  const onNext = () => controller?.next();
  const onJumpToPage = (n: number) => controller?.goToPage(n);
  const onJumpToToc = (href: string) => {
    controller?.goToToc(href);
    showToc = false;
  };
  const onJumpToHighlight = async (h: Highlight) => {
    try { await controller?.goToHighlight(h); } catch (e) {
      console.error('jumpToHighlight_failed', e);
      toast.error('Could not jump to highlight');
    }
    showHighlights = false;
  };
  const onSaveHighlight = async (color: string) => {
    if (!controller || !book) return;
    const draft = await controller.createHighlight(color);
    if (!draft) return;
    const payload = { ...draft, book_id: book.id };
    try {
      const saved = await highlightsApi.create(payload);
      highlights = [...highlights, saved];
      controller.applyHighlights(highlights);
      selectedText = '';
      selectedCfi = '';
    } catch (e) {
      console.error('saveHighlight_failed', e);
    }
  };
  const onDeleteHighlight = async (highlightId: number) => {
    if (!await confirm({
      title: $t('delete_highlight'),
      message: $t('delete_highlight_confirm'),
    })) return;
    try {
      await highlightsApi.delete(highlightId);
      highlights = highlights.filter((h) => h.id !== highlightId);
      controller?.applyHighlights(highlights);
    } catch (e) {
      console.error('deleteHighlight_failed', e);
      toast.error($t('delete_highlight_failed') ?? 'Could not delete highlight');
    }
  };
  const onSetFontSize = (delta: number) => {
    fontSizeRem = Math.max(0.75, Math.min(2.0, fontSizeRem + delta * 0.0625));
    controller?.setFontSize(fontSizeRem);
  };
  const onSetFontFamily = (f: 'serif' | 'sans') => {
    fontFamily = f;
    controller?.setFontFamily(f);
  };
  const onSetLineHeight = (lh: number) => {
    lineHeight = lh;
    controller?.setLineHeight(lh);
  };
  const onSetTheme = (t: 'light' | 'sepia' | 'dark') => {
    setReaderTheme(t);
    controller?.setTheme(t);
  };
  const onClose = () => goto(`/books/${id}`);
  const onToggleToc = () => { showToc = !showToc; };
  const onToggleHighlights = () => { showHighlights = !showHighlights; };

  // Sync the jump input's controlled value with the current page.
  $effect(() => {
    const p = displayPage;
    const nav = lastNavigatedPage;
    pageInputValue = p;
  });

  // --- Window-level key/touch handlers (format-agnostic) ---
  function handleKeyDown(e: KeyboardEvent) {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
    if (e.key === 'Escape') {
      if (showToc || showHighlights) {
        showToc = false; showHighlights = false;
        e.preventDefault();
      }
      return;
    }
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') { onPrev(); e.preventDefault(); }
    else if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { onNext(); e.preventDefault(); }
    else if (e.key === 'Home') { onJumpToPage(1); e.preventDefault(); }
    else if (e.key === 'End') { onJumpToPage(displayTotal); e.preventDefault(); }
  }

  // Touch swipe heuristic — same as monolith 99-134, but it now
  // calls onPrev()/onNext() instead of prevPage()/nextPage().
  let touchStartX = 0, touchStartY = 0, touchIsScrolling = false;
  const SWIPE_MIN_DISTANCE = 80;
  const SCROLL_LOCK_THRESHOLD = 20;
  function handleTouchStart(e: TouchEvent) { touchStartX = e.touches[0].clientX; touchStartY = e.touches[0].clientY; touchIsScrolling = false; }
  function handleTouchMove(e: TouchEvent) {
    if (touchIsScrolling) return;
    const diffX = e.touches[0].clientX - touchStartX;
    const diffY = e.touches[0].clientY - touchStartY;
    if (Math.abs(diffY) > SCROLL_LOCK_THRESHOLD && Math.abs(diffY) > Math.abs(diffX)) touchIsScrolling = true;
  }
  function handleTouchEnd(e: TouchEvent) {
    if (touchIsScrolling) return;
    const diffX = e.changedTouches[0].clientX - touchStartX;
    const diffY = e.changedTouches[0].clientY - touchStartY;
    if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > SWIPE_MIN_DISTANCE) {
      if (diffX > 0) onPrev(); else onNext();
    }
  }
</script>

<svelte:window on:keydown={handleKeyDown} on:touchstart={handleTouchStart} on:touchmove={handleTouchMove} on:touchend={handleTouchEnd} />
<svelte:head><title>{book?.title || $t('reading_loading')}</title></svelte:head>

<div class="flex flex-col relative" data-theme={$readerTheme} style="background: var(--bg); color: var(--text); height: var(--app-h);">
  <ReaderToolbar
    {book} {progressPct}
    currentPage={displayPage} totalPages={displayTotal}
    {pageInputValue} pageInputTotal={displayTotal} {pageInputDisabled}
    fontSize={Math.round(fontSizeRem * 16)}
    {fontFamily} {lineHeight} {toc}
    {showToc} {showHighlights} {highlights} {selectedCfi}
    bookFormatType={bookFormat?.type ?? null}
    onPrev={onPrev} onNext={onNext}
    onFontSize={onSetFontSize}
    onFontFamily={onSetFontFamily}
    onLineHeight={onSetLineHeight}
    onTheme={onSetTheme}
    onToggleToc={onToggleToc}
    onToggleHighlights={onToggleHighlights}
    onSaveHighlight={onSaveHighlight}
    onJumpToToc={onJumpToToc}
    onClose={onClose}
    onJumpToPage={onJumpToPage}
    onDeleteHighlight={onDeleteHighlight}
    onJumpToHighlight={onJumpToHighlight}
  />
  <div class="flex-1 min-h-0 overflow-auto" style="-webkit-overflow-scrolling: touch; overscroll-behavior: contain;" bind:this={container}>
    <div bind:this={bookElement}
      class="mx-auto p-2 md:p-6 w-full h-full min-h-0"
      class:max-w-3xl={bookFormat?.type !== 'pdf' && bookFormat?.type !== 'cbz'}
      class:max-w-none={bookFormat?.type === 'pdf' || bookFormat?.type === 'cbz'}
      style="touch-action: pinch-zoom pan-y;"
    ></div>
  </div>
</div>

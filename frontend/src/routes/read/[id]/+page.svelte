<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { page } from '$app/stores';
  import { books as booksApi, reader as readerApi, highlights as highlightsApi } from '$api/client';
  import { readerTheme, setReaderTheme } from '$stores/auth';
  import type { BookDetail, ProgressRead } from '$api/types';
  import { goto } from '$app/navigation';
  import ReaderToolbar from '$components/ReaderToolbar.svelte';
  import { t } from '$stores/i18n';

  let book = $state<BookDetail | null>(null);
  let progress = $state<ProgressRead | null>(null);
  let container: HTMLDivElement = $state() as HTMLDivElement;
  let bookElement: HTMLElement = $state() as HTMLElement;

  // Reader state
  let fontSize = $state(18);
  let fontFamily = $state<'serif' | 'sans'>('serif');
  let lineHeight = $state(1.7);
  let currentPage = $state(0);
  let totalPages = $state(0);
  let toc = $state<{ id: string; label: string; href?: string }[]>([]);
  let showToc = $state(false);
  let showHighlights = $state(false);
  let highlights = $state<any[]>([]);
  let selectedText = $state('');
  let selectedCfi = $state('');

  let bookInstance: any = null;
  let rendition: any = null;
  let pdfDoc: any = null;
  let currentPageNum = $state(1);

  let pdfScale = $state(1.5);
  let id = $derived(parseInt($page.params.id || '0'));

  $effect(() => {
    if (rendition && $readerTheme) {
      const bg = $readerTheme === 'dark' ? '#000000' : $readerTheme === 'sepia' ? '#F4ECD8' : '#F5F1E8';
      const fg = $readerTheme === 'dark' ? '#F3EFE9' : $readerTheme === 'sepia' ? '#5B4636' : '#2A2622';
      rendition.themes.override('color', fg, true);
      rendition.themes.override('background', bg, true);
    }
  });

  let touchStartX = 0;
  let touchStartY = 0;

  function handleTouchStart(e: TouchEvent) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
  }

  function handleTouchEnd(e: TouchEvent) {
    const diffX = e.changedTouches[0].clientX - touchStartX;
    const diffY = e.changedTouches[0].clientY - touchStartY;
    
    // Swipe left (next page) or swipe right (prev page)
    if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {
      if (diffX > 0) {
        prevPage();
      } else {
        nextPage();
      }
    }
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
      return;
    }
    if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
      prevPage();
      event.preventDefault();
    } else if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ' ') {
      nextPage();
      event.preventDefault();
    }
  }

  let bookFormat = $derived.by(() => {
    if (!book) return null;
    // Pick best format for reader
    const formats = book.formats.map((f) => f.fmt.toUpperCase());
    if (formats.includes('EPUB')) return { type: 'epub', url: `/api/reader/${id}/file/book.epub?fmt=EPUB` };
    if (formats.includes('PDF')) return { type: 'pdf', url: `/api/reader/${id}/file?fmt=PDF` };
    if (formats.includes('FB2')) return { type: 'fb2', url: `/api/reader/${id}/file/book.epub?fmt=FB2` };
    if (formats.includes('RTF')) return { type: 'rtf', url: `/api/reader/${id}/file/book.epub?fmt=RTF` };
    if (formats.includes('TXT')) return { type: 'txt', url: `/api/reader/${id}/file/book.epub?fmt=TXT` };
    // Fallback: convert
    return { type: 'epub', url: `/api/reader/${id}/file/book.epub` };
  });

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

    // Wait for the next tick so that `bookElement` (bound via bind:this) is
    // mounted to the DOM and has a measurable size before EPUB.js / PDF.js
    // tries to render into it.
    await tick();

    if (!bookElement) {
      console.error('read_page_no_book_element');
      return;
    }

    try {
      await initReader();
    } catch (e) {
      console.error('read_page_init_failed', e);
    }
  });

  onDestroy(() => {
    if (rendition) {
      try { rendition.destroy(); } catch {}
    }
    if (pdfDoc) {
      try { pdfDoc.destroy(); } catch {}
    }
  });

  async function initReader() {
    if (!bookFormat) return;
    if (bookFormat.type === 'epub') {
      await initEpubReader();
    } else if (bookFormat.type === 'pdf') {
      await initPdfReader();
    } else if (['fb2', 'rtf', 'txt'].includes(bookFormat.type)) {
      initTextReader();
    }
  }

  async function initEpubReader() {
    const ePub = (await import('epubjs')).default;
    bookInstance = ePub(bookFormat!.url);
    rendition = bookInstance.renderTo(bookElement, {
      width: '100%',
      height: '100%',
      spread: 'none',
      manager: 'default',
      flow: 'paginated',
    });

    rendition.hooks.content.register((contents: any) => {
      const doc = contents.document;
      doc.addEventListener('keydown', handleKeyDown);
      doc.addEventListener('touchstart', handleTouchStart);
      doc.addEventListener('touchend', handleTouchEnd);
    });

    // Apply theme
    rendition.themes.fontSize(`${fontSize}px`);
    if (typeof rendition.themes.font === 'function') {
      rendition.themes.font(fontFamily === 'serif' ? '"Source Serif Pro", Georgia, serif' : 'Inter, system-ui, sans-serif');
    }

    // Apply reader theme. `themes.override(name, value, important)` — the
    // `!important` flag is the THIRD argument, not embedded in the value
    // string. Passing "!important" inside the value produces invalid CSS
    // and the override is dropped, leaving the EPUB's own (black) text color.
    const themeColors = $readerTheme === 'dark'
      ? { bg: '#000000', fg: '#F3EFE9' }
      : $readerTheme === 'sepia'
      ? { bg: '#F4ECD8', fg: '#5B4636' }
      : { bg: '#F5F1E8', fg: '#2A2622' };
    rendition.themes.override('color', themeColors.fg, true);
    rendition.themes.override('background', themeColors.bg, true);
    // Also force paragraphs/links/headings in case the EPUB styles them
    rendition.themes.override('a', { 'color': 'inherit', 'text-decoration': 'underline' }, false);

    // Restore progress
    try {
      if (progress && progress.position) {
        try {
          await rendition.display(progress.position);
        } catch {
          await rendition.display();
        }
      } else {
        await rendition.display();
      }
    } catch (e) {
      console.error('epub_display_failed', e);
      // Last-resort fallback
      try { await rendition.display(); } catch {}
    }

    // Track location. The locations index is generated asynchronously below
    // (in `bookInstance.ready.then(...)`), so guarding `percentageFromCfi`
    // prevents a noisy "locations not generated" error on the first few events.
    rendition.on('relocated', (location: any) => {
      try {
        const cfi = location.start.cfi;
        const pct = (bookInstance.locations && bookInstance.locations.length)
          ? bookInstance.locations.percentageFromCfi(cfi)
          : 0;
        currentPage = Math.round(pct * 100);
        saveProgress(cfi, pct);
      } catch (e) {
        // Locations might not be ready yet — silent.
      }
    });

    // Get TOC
    bookInstance.loaded.navigation.then((nav: any) => {
      toc = (nav.toc || []).map((item: any) => ({
        id: item.id,
        label: item.label,
        href: item.href,
      }));
    }).catch((e: any) => console.error('toc_load_failed', e));

    // Generate locations for progress %
    bookInstance.ready.then(() => {
      bookInstance.locations.generate(1024);
    }).catch((e: any) => console.error('locations_generate_failed', e));

    // Track selection for highlights
    rendition.on('selected', (cfiRange: string, contents: any) => {
      const sel = contents.window.getSelection();
      selectedText = sel ? sel.toString() : '';
      selectedCfi = cfiRange;
      if (selectedText) {
        showHighlightMenu(contents, cfiRange);
      }
    });

    // Load existing highlights
    try {
      highlights = await highlightsApi.list(id);
      applyHighlights();
    } catch (e) {
      console.error('highlights_load_failed', e);
    }
  }

  function applyHighlights() {
    if (!rendition) return;
    // Remove existing
    highlights.forEach((h) => {
      try {
        rendition.annotations.remove(h.cfi, 'highlight');
      } catch {}
    });
    // Re-add
    highlights.forEach((h) => {
      try {
        rendition.annotations.add('highlight', h.cfi, {}, null, 'alejandria-highlight', {
          fill: highlightColor(h.color),
        });
      } catch {}
    });
  }

  function highlightColor(name: string) {
    return {
      yellow: 'rgba(255, 213, 79, 0.4)',
      green: 'rgba(129, 199, 132, 0.4)',
      blue: 'rgba(100, 181, 246, 0.4)',
      pink: 'rgba(244, 143, 177, 0.4)',
      orange: 'rgba(255, 171, 64, 0.4)',
    }[name] || 'rgba(255, 213, 79, 0.4)';
  }

  function showHighlightMenu(contents: any, cfiRange: string) {
    // Inject a small floating menu
    rendition.annotations.add('highlight', cfiRange, {}, null, 'alejandria-highlight', {
      fill: highlightColor('yellow'),
    });
  }

  async function saveHighlight(color = 'yellow') {
    if (!selectedCfi || !selectedText || !book) return;
    try {
      const h = await highlightsApi.create({
        book_id: book.id,
        cfi: selectedCfi,
        text: selectedText,
        color,
      });
      highlights = [...highlights, h];
      applyHighlights();
      selectedText = '';
      selectedCfi = '';
    } catch (e) {
      console.error(e);
    }
  }

  async function initPdfReader() {
    const pdfjs = await import('pdfjs-dist');
    // Use the worker
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.mjs',
      import.meta.url
    ).toString();

    const loadingTask = pdfjs.getDocument(bookFormat!.url);
    pdfDoc = await loadingTask.promise;
    totalPages = pdfDoc.numPages;

    try {
      const page = await pdfDoc.getPage(1);
      const baseViewport = page.getViewport({ scale: 1.0 });
      const targetWidth = container ? (container.clientWidth - 48) : 800;
      const fitScale = targetWidth / baseViewport.width;
      pdfScale = Math.min(2.0, Math.max(1.0, fitScale));
      fontSize = Math.round((pdfScale - 1.0) / 0.075 + 12);
    } catch (e) {
      console.error("Error calculating PDF fit scale:", e);
    }

    await renderPage(progress?.position ? parseInt(progress.position) : 1);
  }

  async function renderPage(pageNum: number) {
    if (!pdfDoc || pageNum < 1 || pageNum > pdfDoc.numPages) return;
    currentPageNum = pageNum;
    const page = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: pdfScale });
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    canvas.className = 'max-w-full shadow-soft rounded';
    bookElement.innerHTML = '';
    bookElement.appendChild(canvas);
    await page.render({ canvasContext: ctx, viewport }).promise;
    // Update progress
    const pct = (pageNum - 1) / pdfDoc.numPages;
    saveProgress(String(pageNum), pct, 'page');
  }

  function initTextReader() {
    fetch(bookFormat!.url)
      .then((r) => r.text())
      .then((text) => {
        const div = document.createElement('div');
        div.className = 'reader';
        div.innerHTML = text
          .split('\n\n')
          .map((p) => `<p>${escapeHtml(p)}</p>`)
          .join('');
        bookElement.innerHTML = '';
        bookElement.appendChild(div);
      });
  }

  function escapeHtml(s: string) {
    return s.replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    } as any)[c]);
  }

  function saveProgress(position: string, pct: number, type: string = 'cfi') {
    if (!book) return;
    readerApi.updateProgress({
      book_id: book.id,
      position,
      position_type: type as any,
      progress_pct: pct,
    }).catch(() => {});
  }

  function nextPage() {
    if (bookFormat?.type === 'epub' && rendition) {
      rendition.next();
    } else if (bookFormat?.type === 'pdf' && pdfDoc) {
      renderPage(currentPageNum + 1);
    }
  }

  function prevPage() {
    if (bookFormat?.type === 'epub' && rendition) {
      rendition.prev();
    } else if (bookFormat?.type === 'pdf' && pdfDoc) {
      renderPage(currentPageNum - 1);
    }
  }

  function setFontSize(delta: number) {
    fontSize = Math.max(12, Math.min(32, fontSize + delta));
    if (rendition) {
      rendition.themes.fontSize(`${fontSize}px`);
    } else if (pdfDoc) {
      pdfScale = 1.0 + (fontSize - 12) * 0.075;
      renderPage(currentPageNum);
    }
  }

  function changeReaderTheme(t: 'light' | 'sepia' | 'dark') {
    setReaderTheme(t);
    if (rendition) {
      const bg = t === 'dark' ? '#000000' : t === 'sepia' ? '#F4ECD8' : '#F5F1E8';
      const fg = t === 'dark' ? '#F3EFE9' : t === 'sepia' ? '#5B4636' : '#2A2622';
      rendition.themes.override('color', fg, true);
      rendition.themes.override('background', bg, true);
    }
  }
</script>

<svelte:window on:keydown={handleKeyDown} on:touchstart={handleTouchStart} on:touchend={handleTouchEnd} />

<svelte:head>
  <title>{book?.title || $t('reading_loading')}</title>
</svelte:head>

<div class="h-screen flex flex-col" data-theme={$readerTheme} style="background: var(--bg); color: var(--text);">
  <ReaderToolbar
    {book}
    progressPct={bookFormat?.type === 'pdf' ? (currentPageNum - 1) / Math.max(1, totalPages) : currentPage / 100}
    currentPage={bookFormat?.type === 'pdf' ? currentPageNum : currentPage}
    totalPages={bookFormat?.type === 'pdf' ? totalPages : 100}
    {fontSize}
    {fontFamily}
    {lineHeight}
    {toc}
    {showToc}
    {showHighlights}
    {highlights}
    on:prev={prevPage}
    on:next={nextPage}
    on:fontSize={(e) => setFontSize(e.detail)}
    on:fontFamily={(e) => { fontFamily = e.detail; if (rendition && typeof rendition.themes.font === 'function') rendition.themes.font(e.detail === 'serif' ? '"Source Serif Pro", Georgia, serif' : 'Inter, system-ui, sans-serif'); }}
    on:lineHeight={(e) => { lineHeight = e.detail; if (rendition) rendition.themes.default({ lineHeight: e.detail }); }}
    on:theme={(e) => changeReaderTheme(e.detail)}
    on:toggleToc={() => (showToc = !showToc)}
    on:toggleHighlights={() => (showHighlights = !showHighlights)}
    on:saveHighlight={(e) => saveHighlight(e.detail)}
    on:close={() => goto(`/books/${id}`)}
  />

  <div class="flex-1 min-h-0 overflow-auto" bind:this={container}>
    <div
      bind:this={bookElement}
      class="mx-auto p-6 w-full h-full"
      class:max-w-3xl={bookFormat?.type !== 'pdf'}
      class:max-w-none={bookFormat?.type === 'pdf'}
    ></div>
  </div>
</div>

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

  let book = $state<BookDetail | null>(null);
  let progress = $state<ProgressRead | null>(null);
  let container: HTMLDivElement = $state() as HTMLDivElement;
  let bookElement: HTMLElement = $state() as HTMLElement;

  // EPUB virtual-page index state (Feature 1: jump-to-page).
  // epubTotalPages is 0 until locations.generate(1024) resolves, at which
  // point it holds the real virtual-page count (replaces the previous
  // fake `100` denominator). epubCurrentPage is updated by the
  // `relocated` listener once locations are ready. The input in the
  // toolbar is disabled while locationsReady is false.
  let epubTotalPages = $state(0);
  let epubCurrentPage = $state(1);
  let locationsReady = $state(false);
  // Controlled value for the jump-to-page <input>. Synced to the
  // current display page via $effect so prev/next/jump always reflect
  // back into the field.
  let pageInputValue = $state(1);
  // Sentinel incremented every time the page actually changes (via
  // prev/next/jumpToHighlight/TOC jump). The $effect below reads it so
  // it only re-syncs pageInputValue from displayPage on navigation,
  // NOT on every keystroke in the input (which would clobber the
  // user's typed value).
  let lastNavigatedPage = $state(0);
  // Re-entrancy flag for goToPage — last dispatched jump wins.
  let jumping = false;

  // Reader state. fontSize is now tracked in *rem* instead of px so the
  // user's iOS/Android "Larger Text" preference scales the reader text
  // proportionally (1rem = the user-agent root font size, which the OS
  // already scales on mobile when text-size-adjust is honored).
  let fontSizeRem = $state(1.125);
  let fontFamily = $state<'serif' | 'sans'>('serif');
  let lineHeight = $state(1.7);
  let currentPage = $state(0);
  let totalPages = $state(0);
  let toc = $state<{ id: string; label: string; href?: string }[]>([]);
  let showToc = $state(false);
  let showHighlights = $state(false);
  let highlights = $state<Highlight[]>([]);
  let selectedText = $state('');
  let selectedCfi = $state('');

  let bookInstance: any = null;
  let rendition: any = null;
  let pdfDoc: any = null;
  let currentPageNum = $state(1);

  // CBZ state — array of object URLs (one per image page) and the
  // current page number. Object URLs are revoked on destroy so the
  // browser doesn't leak 100s of MB of decoded bitmaps.
  let cbzPages: string[] = [];
  let cbzScale = $state(1.0);

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
  // Tracks whether the current touch gesture has already been classified
  // as a vertical scroll. Once a touchmove shows the user is scrolling
  // up/down (|diffY| > |diffX| by a comfortable margin), we set this
  // flag and stop trying to detect a page-turn swipe. This prevents the
  // annoying "I scrolled, and a page changed anyway" feel on mobile,
  // because the swipe decision now happens during the gesture, not
  // after the scroll is already done.
  let touchIsScrolling = false;
  // Minimum horizontal travel (in CSS pixels) to count as a swipe. Bumped
  // from 50 → 80 because the previous threshold fired on casual finger
  // drift during a vertical scroll.
  const SWIPE_MIN_DISTANCE = 80;
  // Once |diffY| exceeds this value during a gesture, we lock the
  // gesture in as a scroll and never reconsider it as a swipe. Set to
  // 20px so the decision happens almost immediately on the first
  // significant vertical move, not after a long scroll.
  const SCROLL_LOCK_THRESHOLD = 20;

  function handleTouchStart(e: TouchEvent) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    touchIsScrolling = false;
  }

  function handleTouchMove(e: TouchEvent) {
    if (touchIsScrolling) return;
    const diffX = e.touches[0].clientX - touchStartX;
    const diffY = e.touches[0].clientY - touchStartY;
    // Lock the gesture in as a vertical scroll as soon as the user
    // moves more vertically than horizontally by the lock threshold.
    // After this point we no longer consider a page-turn swipe, even
    // if the user reverses direction mid-gesture.
    if (Math.abs(diffY) > SCROLL_LOCK_THRESHOLD && Math.abs(diffY) > Math.abs(diffX)) {
      touchIsScrolling = true;
    }
  }

  function handleTouchEnd(e: TouchEvent) {
    if (touchIsScrolling) return;
    const diffX = e.changedTouches[0].clientX - touchStartX;
    const diffY = e.changedTouches[0].clientY - touchStartY;
    // Swipe left (next page) or swipe right (prev page). The
    // requirement is now: horizontal travel > SWIPE_MIN_DISTANCE AND
    // the gesture was never reclassified as a scroll. This kills the
    // false-positive page-changes that happened when the user's
    // finger drifted sideways while scrolling vertically.
    if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > SWIPE_MIN_DISTANCE) {
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
    // ESC closes any open drawer (TOC or Highlights). On mobile this
    // is the only way to dismiss the drawer if the user can't see
    // the X button.
    if (event.key === 'Escape') {
      if (showToc || showHighlights) {
        showToc = false;
        showHighlights = false;
        event.preventDefault();
        return;
      }
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
    if (formats.includes('CBZ')) return { type: 'cbz', url: `/api/reader/${id}/file?fmt=CBZ` };
    if (formats.includes('CBR')) return { type: 'cbz', url: `/api/reader/${id}/file?fmt=CBR` };
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
      // Detach the resize listeners we registered in initPdfReader.
      // Without this, every visit to a PDF would leak listeners.
      if (typeof window !== 'undefined') {
        window.visualViewport?.removeEventListener('resize', refitOnResize);
        window.removeEventListener('orientationchange', refitOnResize);
        window.removeEventListener('resize', refitOnResize);
      }
    }
    if (cbzPages.length) {
      for (const u of cbzPages) {
        try { URL.revokeObjectURL(u); } catch {}
      }
      cbzPages = [];
    }
  });

  async function initReader() {
    if (!bookFormat) return;
    if (bookFormat.type === 'epub') {
      await initEpubReader();
    } else if (bookFormat.type === 'pdf') {
      await initPdfReader();
    } else if (bookFormat.type === 'cbz') {
      await initCbzReader();
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
      doc.addEventListener('touchmove', handleTouchMove);
      doc.addEventListener('touchend', handleTouchEnd);
      // Propagate the theme into the EPUB iframe. The iframe is a
      // separate document — it does NOT inherit our `data-theme`
      // attribute or our CSS variables. We mirror the chosen theme
      // onto the iframe's documentElement so any EPUB-authored CSS
      // that uses `var(--bg)` / `var(--text)` picks up the right
      // colors, and we set the body bg/fg as a final fallback for
      // EPUBs that style via inline color instead of variables.
      const root = doc.documentElement;
      root.setAttribute('data-theme', $readerTheme);
      const colors = $readerTheme === 'dark'
        ? { bg: '#000000', fg: '#F3EFE9' }
        : $readerTheme === 'sepia'
        ? { bg: '#F4ECD8', fg: '#5B4636' }
        : { bg: '#F5F1E8', fg: '#2A2622' };
      root.style.setProperty('--bg', colors.bg);
      root.style.setProperty('--text', colors.fg);
      doc.body.style.background = colors.bg;
      doc.body.style.color = colors.fg;
    });

    // Apply theme. fontSize is in rem so the user's iOS/Android "Larger
    // Text" preference scales the EPUB text proportionally.
    rendition.themes.fontSize(`${fontSizeRem}rem`);
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
        // Feature 1: also update the virtual-page index once locations
        // are ready so the jump-to-page input shows the current page.
        // Guarded the same way as percentageFromCfi — the first few
        // relocated events fire before locations exist.
        if (locationsReady && bookInstance.locations && bookInstance.locations.length) {
          try {
            const locIdx = bookInstance.locations.locationFromCfi(cfi);
            if (typeof locIdx === 'number' && locIdx >= 0) {
              const nextPage = Math.min(epubTotalPages, locIdx + 1);
              if (nextPage !== epubCurrentPage) {
                epubCurrentPage = nextPage;
                // Bump the sentinel so the jump-input $effect re-syncs
                // pageInputValue from displayPage. This covers EPUB
                // prev/next, goToPage (rendition.display eventually
                // fires relocated), TOC jumps, and jumpToHighlight —
                // all of which route through this listener.
                lastNavigatedPage++;
              }
            }
          } catch {}
        }
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

    // Generate locations for progress % AND for the jump-to-page input.
    // Wrapped in a 15s timeout (very large EPUBs can hang) with one retry
    // at a smaller chunk size (512 instead of 1024) — epub.js lets us vary
    // the granularity and a coarser index is much faster. On final failure
    // we toast the user so they know why the jump input stayed disabled
    // (previously the error was silent). prev/next still work via
    // rendition's own model even when locations fail.
    const LOCATIONS_TIMEOUT_MS = 15000;
    const generateWithTimeout = (chunk: number) =>
      Promise.race([
        bookInstance.locations.generate(chunk),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error(`locations.generate(${chunk}) timed out after ${LOCATIONS_TIMEOUT_MS}ms`)), LOCATIONS_TIMEOUT_MS)
        ),
      ]);
    bookInstance.ready.then(async () => {
      let lastErr: unknown;
      for (const chunk of [1024, 512]) {
        try {
          await generateWithTimeout(chunk);
          if ((bookInstance.locations.length() || 0) > 0) {
            epubTotalPages = bookInstance.locations.length();
            locationsReady = true;
            return;
          }
        } catch (e) {
          lastErr = e;
          console.error('locations_generate_failed', { chunk, error: e });
        }
      }
      // Both attempts failed — keep input disabled, surface the reason.
      locationsReady = false;
      epubTotalPages = 0;
      console.error('locations_generate_failed_final', lastErr);
      toast.error($t('jump_locations_failed'));
    }).catch((e: any) => {
      console.error('locations_generate_failed', e);
      toast.error($t('jump_locations_failed'));
    });

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
      // Feature 3a: for PDF/CBZ we record the current 1-based page
      // number so the highlights drawer can later jump back to the
      // exact page the user was on. For EPUB the CFI is the source of
      // truth and locations-based virtual pages are not yet wired to
      // this flow — leaving `page` undefined.
      const page = (bookFormat?.type === 'pdf' || bookFormat?.type === 'cbz')
        ? currentPageNum
        : undefined;
      const h = await highlightsApi.create({
        book_id: book.id,
        cfi: selectedCfi,
        text: selectedText,
        color,
        ...(page !== undefined ? { page } : {}),
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

    // Compute initial fit scale. refitPdf() is what handles subsequent
    // resizes (rotate, address bar show/hide, split-screen). We keep
    // this initial computation inline so the first paint is already
    // at the right size — no flash of the 1.5 default.
    try {
      // Wait one extra tick in case the container just got bound to
      // the DOM and `clientWidth` is still 0 — otherwise the fit
      // would lock pdfScale to a wrong value until the next resize.
      await tick();
      const targetWidth = container?.clientWidth || 0;
      if (targetWidth > 0) {
        await refitPdf(targetWidth);
      } else {
        // Last-resort fallback: assume 800. This path should be rare
        // because window.resize below will fix it as soon as the
        // browser paints.
        await refitPdf(800);
      }
    } catch (e) {
      console.error("Error calculating PDF fit scale:", e);
    }

    await renderPage(progress?.position ? parseInt(progress.position) : 1);

    // Refit on viewport changes. visualViewport fires on iOS Safari
    // when the address bar collapses/expands and on Android Chrome
    // when the keyboard appears; orientationchange catches the
    // rotation that visualViewport misses in some browsers; plain
    // window.resize catches the desktop case of dragging the window
    // edge, which fires neither of the above on most browsers.
    if (typeof window !== 'undefined') {
      window.visualViewport?.addEventListener('resize', refitOnResize);
      window.addEventListener('orientationchange', refitOnResize);
      window.addEventListener('resize', refitOnResize);
    }
  }

  /**
   * Recompute pdfScale so the current page's content fits the visible
   * width. Call this whenever the viewport changes (rotate, resize,
   * address bar toggle). Re-renders the current page after recomputing
   * so the new size takes effect immediately — otherwise the old canvas
   * stays at the old pixel size until the user manually turns the page.
   */
  async function refitPdf(targetWidth: number) {
    if (!pdfDoc) return;
    const page = await pdfDoc.getPage(currentPageNum);
    const baseViewport = page.getViewport({ scale: 1.0 });
    // The bookElement has p-2 (8px) horizontal padding on mobile, p-6
    // (24px) on desktop. The actual content width is therefore
    // clientWidth minus 16 (mobile) or 48 (desktop). Using the parent
    // container's clientWidth minus 16 is a safe middle ground.
    const fitScale = targetWidth / baseViewport.width;
    pdfScale = Math.min(2.5, Math.max(0.5, fitScale));
  }

  function refitOnResize() {
    if (!pdfDoc || !container) return;
    const w = container.clientWidth;
    refitPdf(w).then(() => renderPage(currentPageNum)).catch(() => {});
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
    // Render the canvas at its NATIVE pixel size (viewport.width ×
    // viewport.height from PDF.js, already includes pdfScale). We
    // intentionally do NOT add `w-full` here — that would stretch a
    // canvas drawn at 918px up to whatever the container is (1200px
    // on a desktop, 360px on mobile), creating a second CSS scale on
    // top of pdfScale and making the A+/A- buttons feel ineffective.
    // `max-w-full` still caps the canvas at the container width so it
    // never overflows on a narrow viewport. `mx-auto` centers it on
    // wide screens. Touch-action stays pinch-zoom pan-y so the user
    // can use the browser's native pinch gesture as a second zoom
    // channel beyond the A+/A- buttons.
    canvas.className = 'block max-w-full h-auto shadow-soft rounded mx-auto';
    canvas.style.touchAction = 'pinch-zoom pan-y';
    bookElement.innerHTML = '';
    bookElement.appendChild(canvas);
    await page.render({ canvasContext: ctx, viewport }).promise;
    // Update progress
    const pct = (pageNum - 1) / pdfDoc.numPages;
    saveProgress(String(pageNum), pct, 'page');
  }

  // CBZ is a ZIP of images. Fetch once, extract the image entries with
  // JSZip, build object URLs (revoked on destroy), and render one at a
  // time. Images are sorted by filename so a chapter's pages stay in
  // order — readers expect page-001.jpg before page-215.jpg.
  async function initCbzReader() {
    const JSZip = (await import('jszip')).default;
    const resp = await fetch(bookFormat!.url);
    if (!resp.ok) throw new Error(`CBZ fetch failed: ${resp.status}`);
    const buf = await resp.arrayBuffer();
    const zip = await JSZip.loadAsync(buf);

    // Pick image entries only — some CBZ files include ComicInfo.xml
    // or other metadata sidecars we don't want to render.
    const imageExts = new Set(['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'avif']);
    const entries = Object.values(zip.files).filter(
      (f: any) => !f.dir && imageExts.has((f.name.split('.').pop() || '').toLowerCase())
    );
    entries.sort((a: any, b: any) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));

    if (!entries.length) {
      bookElement.innerHTML = '<p class="text-center opacity-70">CBZ sin imágenes legibles.</p>';
      return;
    }

    // Object URLs decoded lazily — JSZip yields Blobs per entry.
    // A 215-page CBZ holds ~5MB of compressed images; we keep them all
    // in memory as object URLs (re-rendering on prev/next is instant).
    // If memory ever becomes an issue, swap to LRU caching.
    const urls: string[] = [];
    for (const entry of entries as any[]) {
      const blob = await entry.async('blob');
      // Preserve mime type — JSZip's async('blob') defaults to
      // application/octet-stream, which most browsers still render
      // but a few (Safari on .webp) reject. Sniff from extension.
      const ext = (entry.name.split('.').pop() || '').toLowerCase();
      const mime = {
        jpg: 'image/jpeg', jpeg: 'image/jpeg',
        png: 'image/png', gif: 'image/gif',
        webp: 'image/webp', bmp: 'image/bmp', avif: 'image/avif',
      }[ext] || 'image/jpeg';
      urls.push(URL.createObjectURL(new Blob([blob], { type: mime })));
    }
    cbzPages = urls;
    totalPages = cbzPages.length;

    // Pick initial page from saved progress (page numbers stored as
    // 1-based strings, matching the PDF reader's scheme).
    const startPage = progress?.position ? Math.max(1, parseInt(progress.position) || 1) : 1;
    renderCbzPage(startPage);
  }

  function renderCbzPage(pageNum: number) {
    if (!cbzPages.length || pageNum < 1 || pageNum > cbzPages.length) return;
    currentPageNum = pageNum;
    const url = cbzPages[pageNum - 1];
    bookElement.innerHTML = '';
    const img = document.createElement('img');
    img.src = url;
    img.alt = `Página ${pageNum}`;
    // The image width is set inline below via `img.style.width =
    // ${cbzScale * 100}%`, so the className intentionally omits
    // `w-full` — including it would force a competing 100% width
    // and then the inline style would fight with the class on every
    // A+/A- press. `max-w-full` is still here as a safety cap so the
    // image never overflows the container when cbzScale < 1.
    img.className = 'block h-auto max-w-full shadow-soft rounded mx-auto';
    // Apply the user's chosen zoom level by overriding `width` as a
    // percentage of the container. cbzScale == 1.0 means fill the
    // container; cbzScale > 1.0 zooms in (image overflows and the
    // user can pan); cbzScale < 1.0 shrinks it. Using `width` (instead
    // of the previous CSS `transform: scale()`) means the image's
    // layout box actually grows, so the container's scroll height
    // updates with it and swipe gestures keep working at all zoom
    // levels.
    img.style.width = `${cbzScale * 100}%`;
    img.style.maxWidth = 'none';
    img.style.transition = 'width 0.15s ease';
    // pinch-zoom pan-y: browser handles two-finger pinch zoom AND
    // vertical pan. Single-finger horizontal swipes still reach our
    // JS handler so page-turn keeps working. Without `pinch-zoom`,
    // the user could not zoom into the manga page with their fingers.
    img.style.touchAction = 'pinch-zoom pan-y';
    bookElement.appendChild(img);
    const pct = (pageNum - 1) / cbzPages.length;
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

  // Feature 1: jump to a user-typed page (1-based) for any format.
  // Clamps out-of-range input and non-numeric input silently so the
  // user never sees a crash — the worst case is "lands on page 1".
  async function goToPage(n: number) {
    const total = displayTotal;
    const target = Math.max(1, Math.min(total, Math.floor(n) || 1));
    jumping = true;
    try {
      if (bookFormat?.type === 'pdf' && pdfDoc) {
        renderPage(target);
        lastNavigatedPage++;
      } else if (bookFormat?.type === 'cbz' && cbzPages.length) {
        renderCbzPage(target);
        lastNavigatedPage++;
      } else if (bookFormat?.type === 'epub' && rendition && bookInstance && locationsReady) {
        const cfi = bookInstance.locations.cfiFromLocation(target - 1);
        if (cfi) {
          await rendition.display(cfi);
          // rendition.display() does NOT synchronously emit `relocated`,
          // so we explicitly save progress + update the virtual page.
          saveProgress(cfi, (target - 1) / Math.max(1, epubTotalPages), 'cfi');
          epubCurrentPage = target;
          lastNavigatedPage++;
        }
      }
    } catch (e) {
      console.error('goToPage_failed', e);
    } finally {
      jumping = false;
    }
  }

  // Feature 3b: jump to a saved highlight's location.
  // EPUB uses the CFI (the rendition's display() handles it natively).
  // PDF/CBZ use the recorded 1-based page number. For highlights created
  // before Feature 3a (where `page` is null) we fall back to page 1
  // rather than guessing from the CFI — the existing `saveProgress`
  // in renderPage/renderCbzPage keeps the progress state consistent.
  async function jumpToHighlight(h: Highlight) {
    try {
      if (bookFormat?.type === 'epub' && rendition) {
        await rendition.display(h.cfi);
      } else if (bookFormat?.type === 'pdf' && pdfDoc) {
        const p = h.page ?? 1;
        renderPage(p);
      } else if (bookFormat?.type === 'cbz' && cbzPages.length) {
        const p = h.page ?? 1;
        renderCbzPage(p);
      }
    } catch (e) {
      console.error('jumpToHighlight_failed', e);
      toast.error('Could not jump to highlight');
    }
    // Always close the drawer — even if the jump failed the user has
    // already taken the action they wanted.
    showHighlights = false;
  }

  // Feature 2: delete a highlight (server + local state + reader).
  // On EPUB we re-apply the remaining highlights to remove the
  // annotation visually; on PDF/CBZ there's nothing in the reader to
  // remove, so we just update local state.
  async function deleteHighlight(id: number) {
    if (!confirm($t('delete_highlight_confirm'))) return;
    try {
      await highlightsApi.delete(id);
      highlights = highlights.filter((h) => h.id !== id);
      if (rendition) {
        // Re-render all remaining highlights — applyHighlights() first
        // removes all known annotations, then re-adds them. The deleted
        // CFI is no longer in `highlights` so it won't come back.
        applyHighlights();
      }
    } catch (e) {
      console.error('deleteHighlight_failed', e);
      toast.error('Could not delete highlight');
    }
  }

  // Feature 1: derived display values for the toolbar indicator and
  // jump input. For EPUB these fall back to the previous "currentPage /
  // 100" scheme while locations are still generating — the input is
  // disabled during that window so the user cannot jump anyway.
  let displayTotal = $derived(
    bookFormat?.type === 'epub' ? (locationsReady ? epubTotalPages : 100) : totalPages
  );
  let displayPage = $derived(
    bookFormat?.type === 'epub'
      ? (locationsReady ? epubCurrentPage : currentPage)
      : currentPageNum
  );
  let progressPct = $derived(
    bookFormat?.type === 'pdf' || bookFormat?.type === 'cbz'
      ? (currentPageNum - 1) / Math.max(1, totalPages)
      : currentPage / 100
  );

  // Sync the jump input's controlled value with the current page so
  // prev/next and successful jumps reflect into the field. Done in an
  // effect (not at the call sites) because the user might also type a
  // value mid-gesture and we don't want prev/next to clobber their
  // input mid-keystroke — the input loses focus on each keystroke,
  // but if it has focus the effect still runs harmlessly because Svelte
  // treats this as a write to the same value (no re-render loop).
  $effect(() => {
    // Read both so the effect tracks them as dependencies. Re-syncs the
    // input from displayPage when navigation happens (lastNavigatedPage
    // changed) or when displayPage itself changes — but NOT when the
    // user types into the input (only pageInputValue changes there).
    const p = displayPage;
    const nav = lastNavigatedPage;
    pageInputValue = p;
  });

  function nextPage() {
    if (bookFormat?.type === 'epub' && rendition) {
      rendition.next();
    } else if (bookFormat?.type === 'pdf' && pdfDoc) {
      renderPage(currentPageNum + 1);
      lastNavigatedPage++;
    } else if (bookFormat?.type === 'cbz' && cbzPages.length) {
      renderCbzPage(currentPageNum + 1);
      lastNavigatedPage++;
    }
  }

  function prevPage() {
    if (bookFormat?.type === 'epub' && rendition) {
      rendition.prev();
    } else if (bookFormat?.type === 'pdf' && pdfDoc) {
      renderPage(currentPageNum - 1);
      lastNavigatedPage++;
    } else if (bookFormat?.type === 'cbz' && cbzPages.length) {
      renderCbzPage(currentPageNum - 1);
      lastNavigatedPage++;
    }
  }

  function setFontSize(delta: number) {
    // delta is the integer the toolbar emits (currently ±2 per click).
    // We treat it as a rem increment: 2 → +0.125rem, -2 → -0.125rem.
    // That moves the reader by ~2px at the default 16px root, which
    // matches the feel of the previous px-based version. The clamp
    // bounds (0.75rem ≈ 12px, 2rem ≈ 32px) match the previous 12-32
    // px range.
    fontSizeRem = Math.max(0.75, Math.min(2.0, fontSizeRem + delta * 0.0625));
    if (rendition) {
      rendition.themes.fontSize(`${fontSizeRem}rem`);
    } else if (pdfDoc) {
      // For PDF/CBZ the A+/A− buttons double as zoom controls. We
      // derive a scale from the same delta so the zoom curve stays
      // consistent: 2 of delta → +0.1 of scale.
      pdfScale = Math.max(0.5, Math.min(2.5, pdfScale + delta * 0.05));
      renderPage(currentPageNum);
    } else if (bookFormat?.type === 'cbz') {
      cbzScale = Math.max(0.5, Math.min(2.5, cbzScale + delta * 0.05));
      renderCbzPage(currentPageNum);
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

<svelte:window on:keydown={handleKeyDown} on:touchstart={handleTouchStart} on:touchmove={handleTouchMove} on:touchend={handleTouchEnd} />

<svelte:head>
  <title>{book?.title || $t('reading_loading')}</title>
</svelte:head>

<!--
  Outer container. We use var(--app-h) (set in app.css to 100dvh where
  supported, 100vh otherwise) instead of h-screen so the mobile address
  bar's appearance/disappearance doesn't leave a dead band at the
  bottom. `relative` is needed so the absolute-positioned scrim
  button (in the toolbar) anchors here.
-->
<div
  class="flex flex-col relative"
  data-theme={$readerTheme}
  style="background: var(--bg); color: var(--text); height: var(--app-h);"
>
  <ReaderToolbar
    {book}
    {progressPct}
    currentPage={displayPage}
    totalPages={displayTotal}
    pageInputValue={pageInputValue}
    pageInputTotal={displayTotal}
    pageInputDisabled={bookFormat?.type === 'epub' && !locationsReady}
    fontSize={Math.round(fontSizeRem * 16)}
    {fontFamily}
    {lineHeight}
    {toc}
    {showToc}
    {showHighlights}
    {highlights}
    selectedCfi={selectedCfi}
    bookFormatType={(bookFormat?.type as 'epub' | 'pdf' | 'cbz' | 'fb2' | 'rtf' | 'txt' | null | undefined) ?? null}
    on:prev={prevPage}
    on:next={nextPage}
    on:fontSize={(e) => setFontSize(e.detail)}
    on:fontFamily={(e) => { fontFamily = e.detail; if (rendition && typeof rendition.themes.font === 'function') rendition.themes.font(e.detail === 'serif' ? '"Source Serif Pro", Georgia, serif' : 'Inter, system-ui, sans-serif'); }}
    on:lineHeight={(e) => { lineHeight = e.detail; if (rendition) rendition.themes.default({ lineHeight: e.detail }); }}
    on:theme={(e) => changeReaderTheme(e.detail)}
    on:toggleToc={() => (showToc = !showToc)}
    on:toggleHighlights={() => (showHighlights = !showHighlights)}
    on:saveHighlight={(e) => saveHighlight(e.detail)}
    on:jumpToToc={(e) => { if (rendition && e.detail) rendition.display(e.detail); showToc = false; }}
    on:close={() => goto(`/books/${id}`)}
    onJumpToPage={(n) => goToPage(n)}
    onDeleteHighlight={(id) => deleteHighlight(id)}
    onJumpToHighlight={(h) => jumpToHighlight(h)}
  />

  <!--
    Reading area. p-2 on mobile, p-6 on desktop: the previous p-6 on a
    360px phone ate 48px of horizontal space. min-h-0 on the inner
    bookElement is the fix for the "tall toolbar pushes the reader off
    screen" edge case — without it, a flex child with h-full can
    grow to its content's intrinsic min-height.
  -->
  <div
    class="flex-1 min-h-0 overflow-auto"
    style="-webkit-overflow-scrolling: touch; overscroll-behavior: contain;"
    bind:this={container}
  >
    <div
      bind:this={bookElement}
      class="mx-auto p-2 md:p-6 w-full h-full min-h-0"
      class:max-w-3xl={bookFormat?.type !== 'pdf' && bookFormat?.type !== 'cbz'}
      class:max-w-none={bookFormat?.type === 'pdf' || bookFormat?.type === 'cbz'}
      style="touch-action: pinch-zoom pan-y;"
    ></div>
  </div>
</div>

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
  let highlights = $state<any[]>([]);
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
      // Without this, every visit to a PDF would leak two listeners.
      if (typeof window !== 'undefined') {
        window.visualViewport?.removeEventListener('resize', refitOnResize);
        window.removeEventListener('orientationchange', refitOnResize);
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

    // Compute initial fit scale. refitPdf() is what handles subsequent
    // resizes (rotate, address bar show/hide, split-screen). We keep
    // this initial computation inline so the first paint is already
    // at the right size — no flash of the 1.5 default.
    try {
      const targetWidth = container ? container.clientWidth : 800;
      await refitPdf(targetWidth);
    } catch (e) {
      console.error("Error calculating PDF fit scale:", e);
    }

    await renderPage(progress?.position ? parseInt(progress.position) : 1);

    // Refit on viewport changes. visualViewport fires on iOS Safari
    // when the address bar collapses/expands and on Android Chrome
    // when the keyboard appears; orientationchange catches the
    // rotation that visualViewport misses in some browsers.
    if (typeof window !== 'undefined') {
      window.visualViewport?.addEventListener('resize', refitOnResize);
      window.addEventListener('orientationchange', refitOnResize);
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
    // `block w-full h-auto` makes the canvas respect the parent's
    // width while preserving its intrinsic aspect ratio. `mx-auto`
    // centers it on wide screens. The previous `max-w-full` only
    // capped the canvas to the container width but did not stretch
    // it, so the canvas kept its old (wrong) pixel size on mobile.
    canvas.className = 'block w-full h-auto max-w-full shadow-soft rounded mx-auto';
    // touch-action: pinch-zoom pan-y lets the browser handle BOTH
    // pinch-to-zoom AND vertical scroll on the canvas. The single-
    // finger horizontal swipe (which we use for page turning) still
    // reaches the JS handler because horizontal pan is not in the
    // allow list. Without `pinch-zoom`, the browser's native two-
    // finger zoom was disabled and the canvas could not be zoomed.
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
    // `block w-full h-auto` makes the image scale to the container's
    // width while keeping the original aspect ratio. The previous
    // `max-w-full` only capped the width but the image kept its
    // intrinsic pixel dimensions, so on a 360px phone the manga page
    // was being clipped at 360px but at 2x its natural resolution.
    img.className = 'block w-full h-auto max-w-full shadow-soft rounded mx-auto';
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

  function nextPage() {
    if (bookFormat?.type === 'epub' && rendition) {
      rendition.next();
    } else if (bookFormat?.type === 'pdf' && pdfDoc) {
      renderPage(currentPageNum + 1);
    } else if (bookFormat?.type === 'cbz' && cbzPages.length) {
      renderCbzPage(currentPageNum + 1);
    }
  }

  function prevPage() {
    if (bookFormat?.type === 'epub' && rendition) {
      rendition.prev();
    } else if (bookFormat?.type === 'pdf' && pdfDoc) {
      renderPage(currentPageNum - 1);
    } else if (bookFormat?.type === 'cbz' && cbzPages.length) {
      renderCbzPage(currentPageNum - 1);
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
    progressPct={(bookFormat?.type === 'pdf' || bookFormat?.type === 'cbz') ? (currentPageNum - 1) / Math.max(1, totalPages) : currentPage / 100}
    currentPage={(bookFormat?.type === 'pdf' || bookFormat?.type === 'cbz') ? currentPageNum : currentPage}
    totalPages={(bookFormat?.type === 'pdf' || bookFormat?.type === 'cbz') ? totalPages : 100}
    fontSize={Math.round(fontSizeRem * 16)}
    {fontFamily}
    {lineHeight}
    {toc}
    {showToc}
    {showHighlights}
    {highlights}
    selectedCfi={selectedCfi}
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

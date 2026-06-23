/**
 * EPUB reader controller (Phase D, item D2).
 *
 * Encapsulates all epub.js lifecycle. The +page orchestrator only
 * talks to this class through the ReaderController interface defined
 * in `./types`.
 *
 * Replaces: +page.svelte's initEpubReader() (lines 238-416 in the
 * pre-phase monolith) plus the EPUB branches of goToPage, nextPage,
 * prevPage, jumpToHighlight, showHighlightMenu, applyHighlights,
 * saveHighlight, saveProgress, and the EPUB portion of the toolbar
 * event handlers.
 */
import type { Highlight } from '$api/types';
import {
  type ReaderController, type ReaderInitOptions, type HighlightDraft,
  type ReaderEvent, type ReaderEventMap,
} from './types';

const LOCATIONS_TIMEOUT_MS = 15000;

/**
 * Convert a #RRGGBB hex string into the rgba string the EPUB.js
 * annotation API expects as the `fill`. Falls back to the default
 * yellow when the input doesn't match a 6-digit hex (a stale legacy
 * "yellow" string, for example).
 */
function hexToRgba(hex: string): string {
  const m = /^#([0-9A-Fa-f]{6})$/.exec(hex);
  if (!m) return 'rgba(255, 213, 79, 0.4)';
  const n = parseInt(m[1], 16);
  const r = (n >> 16) & 0xff;
  const g = (n >> 8) & 0xff;
  const b = n & 0xff;
  return `rgba(${r}, ${g}, ${b}, 0.4)`;
}

export class EpubController implements ReaderController {
  // Reactive state (Svelte 5 $state runes — requires .svelte.ts file)
  currentPage = $state(1);
  totalPages = $state(0);
  currentProgress = $state(0);
  ready = $state(false);
  canGoToPage = $state(false);
  canHighlight = $state(false);

  private book: any = null;
  private rendition: any = null;
  private destroyed = false;
  private containerEl: HTMLElement | null = null;
  private selectedCfi = '';
  private selectedText = '';
  private savedHighlights: Highlight[] = [];
  private listeners = new Map<ReaderEvent, Set<Function>>();

  async init(container: HTMLElement, fileUrl: string, opts: ReaderInitOptions = {}): Promise<void> {
    if (this.destroyed) return;
    this.containerEl = container;
    const ePub = (await import('epubjs')).default;

    const book = ePub(fileUrl);
    this.book = book;
    const rendition = book.renderTo(container, {
      width: '100%',
      height: '100%',
      spread: 'none',
      manager: 'default',
      flow: 'paginated',
    });
    this.rendition = rendition;

    rendition.hooks.content.register((contents: any) => {
      const doc = contents.document;
      // Propagate the theme into the EPUB iframe.
      const root = doc.documentElement;
      const theme = opts.readerTheme ?? 'light';
      root.setAttribute('data-theme', theme);
      const colors = theme === 'dark'
        ? { bg: '#000000', fg: '#F3EFE9' }
        : theme === 'sepia'
        ? { bg: '#F4ECD8', fg: '#5B4636' }
        : { bg: '#F5F1E8', fg: '#2A2622' };
      root.style.setProperty('--bg', colors.bg);
      root.style.setProperty('--text', colors.fg);
      doc.body.style.background = colors.bg;
      doc.body.style.color = colors.fg;
    });

    // Apply initial typography (theme was applied in the content hook above).
    if (opts.initialFontSizeRem) this.setFontSize(opts.initialFontSizeRem);
    if (opts.initialFontFamily) this.setFontFamily(opts.initialFontFamily);
    if (opts.initialLineHeight) this.setLineHeight(opts.initialLineHeight);
    if (opts.readerTheme) this.setTheme(opts.readerTheme);

    // Restore progress — exact same try/catch pattern as monolith 297-311
    try {
      if (opts.savedProgress?.position) {
        try {
          await rendition.display(opts.savedProgress.position);
        } catch {
          await rendition.display();
        }
      } else {
        await rendition.display();
      }
    } catch (e) {
      this.emit('error', { code: 'epub_display_failed', message: 'Failed to display EPUB', cause: e });
      try { await rendition.display(); } catch {}
    }

    // Track location.
    rendition.on('relocated', (location: any) => {
      if (this.destroyed) return;
      try {
        const cfi = location.start.cfi;
        const locs = book.locations;
        const hasLocations = !!locs && (locs.length() || 0) > 0;
        const pct = hasLocations ? locs.percentageFromCfi(cfi) : 0;
        // Always update the percent indicator
        this.currentProgress = pct;

        if (this.canGoToPage && hasLocations) {
          const locIdx = locs.locationFromCfi(cfi);
          if (typeof locIdx === 'number' && locIdx >= 0) {
            const next = Math.min(this.totalPages, locIdx + 1);
            if (next !== this.currentPage) {
              this.currentPage = next;
              this.emit('pagechange', { page: next, total: this.totalPages });
            }
          }
        }
        this.emit('progress', { position: cfi, position_type: 'cfi', progress_pct: pct });
      } catch {}
    });

    // Track selection for highlights.
    rendition.on('selected', (cfiRange: string, contents: any) => {
      if (this.destroyed) return;
      const sel = contents.window.getSelection();
      this.selectedText = sel ? sel.toString() : '';
      this.selectedCfi = cfiRange;
      if (this.selectedText) {
        this.emit('selection', { text: this.selectedText, cfi: cfiRange });
        this.showHighlightMenu(contents, cfiRange);
      }
    });

    // Apply saved highlights if provided.
    if (opts.savedHighlights) this.applyHighlights(opts.savedHighlights);

    // Load TOC and emit.
    book.loaded.navigation.then((nav: any) => {
      if (this.destroyed) return;
      const items = (nav.toc || []).map((item: any) => ({
        id: item.id, label: item.label, href: item.href,
      }));
      this.emit('toc', { items });
    }).catch(() => { this.emit('toc', { items: [] }); });

    // Locations generation — exact same timeout + retry as monolith 366-397
    const generateWithTimeout = (chunk: number) =>
      Promise.race([
        book.locations.generate(chunk),
        new Promise((_, reject) =>
          setTimeout(
            () => reject(new Error(`locations.generate(${chunk}) timed out after ${LOCATIONS_TIMEOUT_MS}ms`)),
            LOCATIONS_TIMEOUT_MS
          )
        ),
      ]);
    book.ready.then(async () => {
      if (this.destroyed) return;
      let lastErr: unknown;
      for (const chunk of [1024, 512]) {
        if (this.destroyed) return;
        try {
          await generateWithTimeout(chunk);
          if ((book.locations.length() || 0) > 0) {
            this.totalPages = book.locations.length();
            this.canGoToPage = true;
            return;
          }
        } catch (e) {
          lastErr = e;
        }
      }
      // Both attempts failed.
      this.canGoToPage = false;
      this.totalPages = 0;
      this.emit('error', { code: 'locations_generate_failed', message: 'Could not build page index', cause: lastErr });
    }).catch((e) => {
      this.emit('error', { code: 'locations_generate_failed', message: 'Could not build page index', cause: e });
    });

    this.canHighlight = true;
    this.ready = true;
    this.emit('ready', undefined as any);
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.canHighlight = false;
    this.ready = false;
    this.canGoToPage = false;
    if (this.rendition) {
      try { this.rendition.destroy(); } catch {}
    }
    if (this.book) {
      try { this.book.destroy(); } catch {}
    }
    this.rendition = null;
    this.book = null;
    this.containerEl = null;
    this.emit('destroy', undefined as any);
    this.listeners.clear();
  }

  async next(): Promise<void> {
    if (this.rendition) await this.rendition.next();
  }
  async prev(): Promise<void> {
    if (this.rendition) await this.rendition.prev();
  }

  async goToPage(n: number): Promise<void> {
    if (!this.rendition || !this.book || !this.canGoToPage) return;
    const target = Math.max(1, Math.min(this.totalPages, Math.floor(n) || 1));
    const cfi = this.book.locations.cfiFromLocation(target - 1);
    if (cfi) {
      await this.rendition.display(cfi);
      this.currentPage = target;
      this.currentProgress = (target - 1) / Math.max(1, this.totalPages);
      this.emit('progress', { position: cfi, position_type: 'cfi', progress_pct: this.currentProgress });
      this.emit('pagechange', { page: target, total: this.totalPages });
    }
  }

  async goToHighlight(h: Highlight): Promise<void> {
    if (!this.rendition || !h.cfi) return;
    await this.rendition.display(h.cfi);
  }

  async goToToc(href: string): Promise<void> {
    if (this.rendition) await this.rendition.display(href);
  }

  async createHighlight(color = 'yellow'): Promise<HighlightDraft | null> {
    if (!this.selectedCfi || !this.selectedText) return null;
    return {
      book_id: 0, // orchestrator fills this in
      cfi: this.selectedCfi,
      text: this.selectedText,
      color,
    };
  }

  async deleteHighlight(_id: number): Promise<void> {
    // No-op on the controller — the orchestrator calls
    // highlightsApi.delete and re-passes the surviving list to
    // applyHighlights.
  }

  async getHighlights(): Promise<Highlight[]> {
    return this.savedHighlights;
  }

  applyHighlights(highlights: Highlight[]): void {
    if (!this.rendition) {
      this.savedHighlights = highlights;
      return;
    }
    this.savedHighlights = highlights;
    // Remove existing annotations, then re-add. The deleted row is no
    // longer in `highlights` so it won't come back.
    for (const h of highlights) {
      try { this.rendition.annotations.remove(h.cfi, 'highlight'); } catch {}
    }
    for (const h of highlights) {
      try {
        this.rendition.annotations.add(
          'highlight',
          h.cfi,
          {},
          null,
          'alejandria-highlight',
          { fill: hexToRgba(h.color), 'data-color': h.color },
        );
      } catch {}
    }
  }

  setFontSize(rem: number): void {
    if (this.rendition) {
      try { this.rendition.themes.fontSize(`${rem}rem`); } catch {}
    }
  }
  setFontFamily(family: 'serif' | 'sans'): void {
    if (this.rendition && typeof this.rendition.themes.font === 'function') {
      const f = family === 'serif'
        ? '"Source Serif Pro", Georgia, serif'
        : 'Inter, system-ui, sans-serif';
      try { this.rendition.themes.font(f); } catch {}
    }
  }
  setLineHeight(value: number): void {
    if (this.rendition) {
      try { this.rendition.themes.default({ lineHeight: value }); } catch {}
    }
  }
  setTheme(theme: 'light' | 'sepia' | 'dark'): void {
    if (!this.rendition) return;
    const bg = theme === 'dark' ? '#000000' : theme === 'sepia' ? '#F4ECD8' : '#F5F1E8';
    const fg = theme === 'dark' ? '#F3EFE9' : theme === 'sepia' ? '#5B4636' : '#2A2622';
    try { this.rendition.themes.override('color', fg, true); } catch {}
    try { this.rendition.themes.override('background', bg, true); } catch {}
  }

  on<E extends ReaderEvent>(event: E, cb: ReaderEventMap[E]): () => void {
    let set = this.listeners.get(event);
    if (!set) {
      set = new Set();
      this.listeners.set(event, set);
    }
    set.add(cb as Function);
    return () => {
      const s = this.listeners.get(event);
      if (s) s.delete(cb as Function);
    };
  }

  private emit<E extends ReaderEvent>(event: E, data: Parameters<ReaderEventMap[E]>[0]): void {
    if (this.destroyed && event !== 'destroy') return;
    const set = this.listeners.get(event);
    if (!set) return;
    for (const cb of set) {
      try { (cb as Function)(data); } catch {}
    }
  }

  private showHighlightMenu(contents: any, cfiRange: string): void {
    if (!this.rendition) return;
    try {
      this.rendition.annotations.add(
        'highlight',
        cfiRange,
        {},
        null,
        'alejandria-highlight',
        { fill: hexToRgba('#FFEB3B') },
      );
    } catch {}
  }
}

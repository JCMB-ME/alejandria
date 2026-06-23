/**
 * CBZ reader controller (Phase D, item D4).
 *
 * Encapsulates jszip + image-page lifecycle. The +page orchestrator
 * only talks to this class through the ReaderController interface
 * defined in `./types`.
 *
 * Replaces: +page.svelte's initCbzReader() + renderCbzPage() (lines
 * 605-686 in the pre-phase monolith) plus the CBZ branches of
 * goToPage, nextPage, prevPage, jumpToHighlight, the CBZ portion of
 * setFontSize, and the cbzPages lifecycle in onDestroy.
 */
import type { Highlight } from '$api/types';
import {
  type ReaderController, type ReaderInitOptions, type HighlightDraft,
  type ReaderEvent, type ReaderEventMap,
} from './types';

const SCALE_MIN = 0.5;
const SCALE_MAX = 2.5;

const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'avif']);
const EXT_TO_MIME: Record<string, string> = {
  jpg: 'image/jpeg', jpeg: 'image/jpeg',
  png: 'image/png', gif: 'image/gif',
  webp: 'image/webp', bmp: 'image/bmp', avif: 'image/avif',
};

export class CbzController implements ReaderController {
  currentPage = $state(1);
  totalPages = $state(0);
  currentProgress = $state(0);
  ready = $state(false);
  canGoToPage = $state(true);
  canHighlight = $state(false);

  private cbzPages: string[] = []; // object URLs
  private cbzScale = $state(1.0);
  private containerEl: HTMLElement | null = null;
  private listeners = new Map<ReaderEvent, Set<Function>>();
  private destroyed = false;

  async init(container: HTMLElement, fileUrl: string, opts: ReaderInitOptions = {}): Promise<void> {
    if (this.destroyed) return;
    this.containerEl = container;
    const JSZip = (await import('jszip')).default;
    const resp = await fetch(fileUrl);
    if (!resp.ok) {
      this.emit('error', { code: 'cbz_fetch_failed', message: `CBZ fetch failed: ${resp.status}` });
      container.innerHTML = '<p class="text-center opacity-70">CBZ failed to load.</p>';
      this.ready = true;
      this.emit('ready', undefined as any);
      return;
    }
    const buf = await resp.arrayBuffer();
    const zip = await JSZip.loadAsync(buf);
    const entries = Object.values(zip.files)
      .filter((f: any) => !f.dir && IMAGE_EXTS.has((f.name.split('.').pop() || '').toLowerCase()))
      .sort((a: any, b: any) =>
        a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
      );

    if (!entries.length) {
      container.innerHTML = '<p class="text-center opacity-70">CBZ has no readable images.</p>';
      this.ready = true;
      this.emit('ready', undefined as any);
      return;
    }

    const urls: string[] = [];
    for (const entry of entries as any[]) {
      if (this.destroyed) {
        for (const u of urls) { try { URL.revokeObjectURL(u); } catch {} }
        return;
      }
      const blob = await entry.async('blob');
      const ext = (entry.name.split('.').pop() || '').toLowerCase();
      const mime = EXT_TO_MIME[ext] || 'image/jpeg';
      urls.push(URL.createObjectURL(new Blob([blob], { type: mime })));
    }
    this.cbzPages = urls;
    this.totalPages = urls.length;

    const startPage = opts.savedProgress?.position
      ? Math.max(1, parseInt(opts.savedProgress.position) || 1)
      : 1;
    this.renderCbzPage(startPage);

    if (opts.savedHighlights) this.applyHighlights(opts.savedHighlights);
    this.canHighlight = true;
    this.ready = true;
    this.emit('ready', undefined as any);
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.canHighlight = false;
    this.ready = false;
    for (const u of this.cbzPages) { try { URL.revokeObjectURL(u); } catch {} }
    this.cbzPages = [];
    this.containerEl = null;
    this.emit('destroy', undefined as any);
    this.listeners.clear();
  }

  async next(): Promise<void> { this.renderCbzPage(this.currentPage + 1); }
  async prev(): Promise<void> { this.renderCbzPage(this.currentPage - 1); }
  async goToPage(n: number): Promise<void> {
    if (!this.cbzPages.length) return;
    const target = Math.max(1, Math.min(this.cbzPages.length, Math.floor(n) || 1));
    this.renderCbzPage(target);
  }

  async goToHighlight(h: Highlight): Promise<void> {
    const p = h.page ?? 1;
    this.renderCbzPage(p);
  }
  async goToToc(_href: string): Promise<void> { /* no-op */ }

  async createHighlight(_color?: string): Promise<HighlightDraft | null> {
    if (!this.cbzPages.length) return null;
    return {
      book_id: 0, // orchestrator fills this in
      cfi: '',
      text: '',
      color: 'yellow',
      page: this.currentPage,
    };
  }

  async deleteHighlight(_id: number): Promise<void> {
    // No-op on the controller — orchestrator handles delete + re-apply.
  }

  async getHighlights(): Promise<Highlight[]> {
    return [];
  }

  applyHighlights(_highlights: Highlight[]): void {
    // No-op for CBZ — there's no annotation layer.
  }

  setFontSize(rem: number): void {
    // The toolbar's font-size A+/A- doubles as zoom for CBZ. The
    // orchestrator already converted the px-delta to a rem value
    // (default 1.125), so we apply the delta from that baseline.
    const delta = rem - 1.125;
    this.cbzScale = Math.max(SCALE_MIN, Math.min(SCALE_MAX, this.cbzScale + delta * 0.5));
    this.renderCbzPage(this.currentPage);
  }
  setFontFamily(_family: 'serif' | 'sans'): void { /* no-op for CBZ */ }
  setLineHeight(_value: number): void { /* no-op for CBZ */ }
  setTheme(_theme: 'light' | 'sepia' | 'dark'): void { /* no-op for CBZ */ }

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
      try { (cb as Function)(data as any); } catch {}
    }
  }

  private renderCbzPage(pageNum: number): void {
    if (!this.cbzPages.length || this.destroyed) return;
    if (pageNum < 1 || pageNum > this.cbzPages.length) return;
    this.currentPage = pageNum;
    const url = this.cbzPages[pageNum - 1];
    if (!this.containerEl) return;
    this.containerEl.innerHTML = '';
    const img = document.createElement('img');
    img.src = url;
    img.alt = `Page ${pageNum}`;
    img.className = 'block h-auto max-w-full shadow-soft rounded mx-auto';
    img.style.width = `${this.cbzScale * 100}%`;
    img.style.maxWidth = 'none';
    img.style.transition = 'width 0.15s ease';
    img.style.touchAction = 'pinch-zoom pan-y';
    this.containerEl.appendChild(img);
    this.currentProgress = (pageNum - 1) / this.cbzPages.length;
    this.emit('pagechange', { page: pageNum, total: this.cbzPages.length });
    this.emit('progress', { position: String(pageNum), position_type: 'page', progress_pct: this.currentProgress });
  }
}

/**
 * Plain-text reader controller (Phase D, item D5).
 *
 * For FB2 / RTF / TXT — formats the backend converts to EPUB and
 * serves back via `/api/reader/{id}/file/book.epub?fmt=FB2`. The
 * server returns the *converted* file as plain text, which we
 * render as a single scrollable text block.
 *
 * Note: the actual file is served as `application/octet-stream` and
 * the body is HTML (the conversion output). This controller
 * historically just dumped the text as paragraphs, which is what we
 * keep doing here.
 *
 * Replaces: +page.svelte's initTextReader() + escapeHtml() (lines
 * 688-707 in the pre-phase monolith).
 */
import type { Highlight } from '$api/types';
import {
  type ReaderController, type ReaderInitOptions, type HighlightDraft,
  type ReaderEvent, type ReaderEventMap,
} from './types';

export class TextController implements ReaderController {
  currentPage = $state(1);
  totalPages = $state(1);
  currentProgress = $state(0);
  ready = $state(false);
  canGoToPage = $state(false);
  canHighlight = $state(false);

  private containerEl: HTMLElement | null = null;
  private listeners = new Map<ReaderEvent, Set<Function>>();
  private destroyed = false;

  async init(container: HTMLElement, fileUrl: string, opts: ReaderInitOptions = {}): Promise<void> {
    if (this.destroyed) return;
    this.containerEl = container;
    try {
      const r = await fetch(fileUrl);
      const text = await r.text();
      const div = document.createElement('div');
      div.className = 'reader';
      div.innerHTML = text
        .split('\n\n')
        .map((p: string) => `<p>${this.escapeHtml(p)}</p>`)
        .join('');
      container.innerHTML = '';
      container.appendChild(div);
    } catch (e) {
      this.emit('error', { code: 'text_fetch_failed', message: 'Could not load text', cause: e });
    }
    if (opts.savedHighlights) this.applyHighlights(opts.savedHighlights);
    this.ready = true;
    this.emit('ready', undefined as any);
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.ready = false;
    this.containerEl = null;
    this.emit('destroy', undefined as any);
    this.listeners.clear();
  }

  // No-op: the monolith has no next/prev for text formats today.
  async next(): Promise<void> {}
  async prev(): Promise<void> {}
  async goToPage(_n: number): Promise<void> {}
  async goToHighlight(_h: Highlight): Promise<void> {}
  async goToToc(_href: string): Promise<void> {}
  async createHighlight(_color?: string): Promise<HighlightDraft | null> { return null; }

  async deleteHighlight(_id: number): Promise<void> {
    // No-op on the controller.
  }

  async getHighlights(): Promise<Highlight[]> {
    return [];
  }

  applyHighlights(_highlights: Highlight[]): void {
    // No-op: text formats have no annotation layer.
  }

  setFontSize(_rem: number): void { /* no-op for text */ }
  setFontFamily(_family: 'serif' | 'sans'): void { /* no-op for text */ }
  setLineHeight(_value: number): void { /* no-op for text */ }
  setTheme(_theme: 'light' | 'sepia' | 'dark'): void { /* no-op for text */ }

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

  private escapeHtml(s: string): string {
    return s.replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    } as Record<string, string>)[c]);
  }
}

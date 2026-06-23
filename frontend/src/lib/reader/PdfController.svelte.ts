/**
 * PDF reader controller (Phase D, item D3).
 *
 * Encapsulates pdfjs-dist lifecycle. The +page orchestrator only
 * talks to this class through the ReaderController interface
 * defined in `./types`.
 *
 * Replaces: +page.svelte's initPdfReader(), refitPdf(), refitOnResize(),
 * renderPage() (lines 480-599 in the pre-phase monolith) plus the PDF
 * branches of goToPage, nextPage, prevPage, jumpToHighlight, the PDF
 * portion of setFontSize, and the resize listeners in onDestroy.
 */
import type { Highlight } from '$api/types';
import {
  type ReaderController, type ReaderInitOptions, type HighlightDraft,
  type ReaderEvent, type ReaderEventMap,
} from './types';

const SCALE_MIN = 0.5;
const SCALE_MAX = 2.5;

export class PdfController implements ReaderController {
  currentPage = $state(1);
  totalPages = $state(0);
  currentProgress = $state(0);
  ready = $state(false);
  canGoToPage = $state(true); // paginated — always true after init
  canHighlight = $state(false);

  private pdfDoc: any = null;
  private pdfScale = $state(1.5);
  private containerEl: HTMLElement | null = null;
  private resizeTeardown: (() => void) | null = null;
  private listeners = new Map<ReaderEvent, Set<Function>>();
  private destroyed = false;

  async init(container: HTMLElement, fileUrl: string, opts: ReaderInitOptions = {}): Promise<void> {
    if (this.destroyed) return;
    this.containerEl = container;
    const pdfjs = await import('pdfjs-dist');
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url
    ).toString();

    const loadingTask = pdfjs.getDocument(fileUrl);
    this.pdfDoc = await loadingTask.promise;
    this.totalPages = this.pdfDoc.numPages;

    // Initial fit.
    try {
      const targetWidth = opts.containerWidth || container.clientWidth || 800;
      await this.refitPdf(targetWidth);
    } catch (e) {
      this.emit('error', { code: 'pdf_fit_failed', message: 'Could not compute fit scale', cause: e });
    }

    const startPage = opts.savedProgress?.position
      ? Math.max(1, parseInt(opts.savedProgress.position) || 1)
      : 1;
    await this.renderPage(startPage);

    // Resize listeners — same three as monolith 522-526.
    if (typeof window !== 'undefined') {
      const refit = () => this.refitOnResize();
      window.visualViewport?.addEventListener('resize', refit);
      window.addEventListener('orientationchange', refit);
      window.addEventListener('resize', refit);
      this.resizeTeardown = () => {
        window.visualViewport?.removeEventListener('resize', refit);
        window.removeEventListener('orientationchange', refit);
        window.removeEventListener('resize', refit);
      };
    }

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
    this.resizeTeardown?.();
    this.resizeTeardown = null;
    if (this.pdfDoc) {
      try { this.pdfDoc.destroy(); } catch {}
    }
    this.pdfDoc = null;
    this.containerEl = null;
    this.emit('destroy', undefined as any);
    this.listeners.clear();
  }

  async next(): Promise<void> { await this.renderPage(this.currentPage + 1); }
  async prev(): Promise<void> { await this.renderPage(this.currentPage - 1); }
  async goToPage(n: number): Promise<void> {
    if (!this.pdfDoc) return;
    const target = Math.max(1, Math.min(this.pdfDoc.numPages, Math.floor(n) || 1));
    await this.renderPage(target);
  }

  async goToHighlight(h: Highlight): Promise<void> {
    const p = h.page ?? 1;
    await this.renderPage(p);
  }
  async goToToc(_href: string): Promise<void> { /* no-op for PDF */ }

  async createHighlight(_color?: string): Promise<HighlightDraft | null> {
    if (!this.pdfDoc) return null;
    return {
      book_id: 0, // orchestrator fills this in
      cfi: '',
      text: '',
      color: 'yellow',
      page: this.currentPage,
    };
  }

  async deleteHighlight(_id: number): Promise<void> {
    // No-op on the controller — the orchestrator handles delete + re-apply.
  }

  async getHighlights(): Promise<Highlight[]> {
    // PDF has no DOM annotation layer; the orchestrator is the
    // source of truth for the list.
    return [];
  }

  applyHighlights(_highlights: Highlight[]): void {
    // No-op for PDF — there's nothing in the reader to annotate.
  }

  setFontSize(rem: number): void {
    // For PDF the A+/A- buttons double as zoom controls. We convert
    // the rem the orchestrator already computed into a scale: each
    // rem ≈ a step of 0.1 of scale.
    if (!this.pdfDoc) return;
    const delta = rem - 1.125; // default rem baseline
    const scaleDelta = delta * 0.8; // rem-→-scale mapping
    this.pdfScale = Math.max(SCALE_MIN, Math.min(SCALE_MAX, this.pdfScale + scaleDelta * 0.05));
    this.renderPage(this.currentPage).catch(() => {});
  }
  setFontFamily(_family: 'serif' | 'sans'): void { /* no-op for PDF */ }
  setLineHeight(_value: number): void { /* no-op for PDF */ }
  setTheme(_theme: 'light' | 'sepia' | 'dark'): void {
    // No-op for PDF — background is set by CSS variables on the
    // container.
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
      try { (cb as Function)(data as any); } catch {}
    }
  }

  private async refitPdf(targetWidth: number): Promise<void> {
    if (!this.pdfDoc) return;
    const page = await this.pdfDoc.getPage(this.currentPage);
    const baseViewport = page.getViewport({ scale: 1.0 });
    const fitScale = targetWidth / baseViewport.width;
    this.pdfScale = Math.min(SCALE_MAX, Math.max(SCALE_MIN, fitScale));
  }

  private refitOnResize(): void {
    if (!this.pdfDoc || !this.containerEl) return;
    const w = this.containerEl.clientWidth;
    this.refitPdf(w).then(() => this.renderPage(this.currentPage)).catch(() => {});
  }

  private async renderPage(pageNum: number): Promise<void> {
    if (!this.pdfDoc || this.destroyed) return;
    if (pageNum < 1 || pageNum > this.pdfDoc.numPages) return;
    this.currentPage = pageNum;
    const page = await this.pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: this.pdfScale });
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    canvas.className = 'block max-w-full h-auto shadow-soft rounded mx-auto';
    canvas.style.touchAction = 'pinch-zoom pan-y';
    if (!this.containerEl) return;
    this.containerEl.innerHTML = '';
    this.containerEl.appendChild(canvas);
    await page.render({ canvasContext: ctx, viewport }).promise;
    this.currentProgress = (pageNum - 1) / this.pdfDoc.numPages;
    this.emit('pagechange', { page: pageNum, total: this.pdfDoc.numPages });
    this.emit('progress', { position: String(pageNum), position_type: 'page', progress_pct: this.currentProgress });
  }
}

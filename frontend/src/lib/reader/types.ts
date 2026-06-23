/**
 * ReaderController contract (Phase D).
 *
 * The public surface every format controller exposes. The +page
 * orchestrator and the ReaderToolbar speak ONLY through this
 * interface — they never check `instanceof EpubController` or
 * reach into format-specific state.
 *
 * Reactive state lives on the controller instance via Svelte 5
 * $state runes (the class lives in a `.svelte.ts` file). The
 * orchestrator forwards `currentPage` / `totalPages` /
 * `currentProgress` into the toolbar by reading the controller's
 * getters in a $derived inside +page.svelte.
 *
 * Contract guarantees:
 *  - `init()` is idempotent for repeat calls in a single component
 *    lifecycle. The +page.svelte calls `init()` exactly once per
 *    `book` change.
 *  - `destroy()` is safe to call before `init()` resolves (e.g.
 *    user navigates away mid-load). It cancels in-flight loads.
 *  - `goToPage()` clamps silently; the orchestrator's
 *    `displayPage` / `displayTotal` clamps as defense-in-depth.
 *  - `on()` returns an unsubscribe function — exactly the
 *    contract the orchestrator uses to clean up in `onDestroy`.
 *  - `createHighlight()` returns `null` when there's nothing to
 *    save; never throws on a missing selection.
 *  - `setFontSize(rem)` is additive: the toolbar emits a delta
 *    (±2); the orchestrator converts to absolute rem, then calls
 *    `controller.setFontSize(rem)`.
 */
import type { Highlight } from '$api/types';

export type BookFormatType =
  | 'epub' | 'pdf' | 'cbz' | 'fb2' | 'rtf' | 'txt';

/** Request body for `highlightsApi.create`. */
export interface HighlightDraft {
  book_id: number;
  cfi: string;
  text: string;
  color: string;
  /** 1-based page; PDF/CBZ only. EPUB leaves undefined. */
  page?: number;
}

export interface ReaderInitOptions {
  /** Saved progress from the backend (null = no saved progress). */
  savedProgress?: { position: string; position_type: 'cfi' | 'page' | 'loc' } | null;
  /** Saved highlights to render on init. */
  savedHighlights?: Highlight[];
  /** Initial reader theme — controllers mirror it onto their iframe / canvas. */
  readerTheme?: 'light' | 'sepia' | 'dark';
  /** Font size in rem; PDF/CBZ ignore. */
  initialFontSizeRem?: number;
  /** 'serif' | 'sans'; PDF/CBZ ignore. */
  initialFontFamily?: 'serif' | 'sans';
  /** Line height; PDF/CBZ ignore. */
  initialLineHeight?: number;
  /** The container's measured width (for PDF initial fit). */
  containerWidth?: number;
}

export type ReaderEvent =
  | 'ready'
  | 'pagechange'
  | 'progress'
  | 'selection'
  | 'highlight'
  | 'error'
  | 'destroy'
  | 'toc';

export type ReaderEventMap = {
  ready: () => void;
  /** Fired after currentPage or progress actually changed (not on
   *  no-op moves — e.g. pressing prev on page 1). */
  pagechange: (data: { page: number; total: number }) => void;
  /** Fired on every progress update (more frequent than pagechange). */
  progress: (data: { position: string; position_type: 'cfi' | 'page' | 'loc'; progress_pct: number }) => void;
  /** Fired when the user makes a text selection. */
  selection: (data: { text: string; cfi: string }) => void;
  /** Fired after the controller has added a highlight to its own DOM
   *  (in addition to returning it from createHighlight). */
  highlight: (data: { highlight: Highlight }) => void;
  error: (data: { code: string; message: string; cause?: unknown }) => void;
  destroy: () => void;
  /** EPUB only — fired once `book.loaded.navigation.then` resolves. */
  toc: (data: { items: { id: string; label: string; href?: string }[] }) => void;
};

export interface ReaderController {
  /** Read-only reactive state — updated as the user navigates. */
  readonly currentPage: number;
  readonly totalPages: number;
  readonly currentProgress: number; // 0..1
  /** True after init() resolves; false during init or after destroy(). */
  readonly ready: boolean;
  /** True when the controller is in a state where goToPage(N) is valid
   *  (e.g. EPUB has finished generating locations). For paginated
   *  formats this is true from the moment init() resolves. */
  readonly canGoToPage: boolean;
  /** True once the controller can synthesise a highlight draft. EPUB
   *  once the rendition exists; PDF/CBZ once the file loaded. */
  readonly canHighlight: boolean;

  /** Lifecycle. init() may take seconds for large EPUBs. */
  init(container: HTMLElement, fileUrl: string, opts?: ReaderInitOptions): Promise<void>;
  destroy(): void;

  /** Navigation. Clamping is the controller's responsibility — pass
   *  any number; the controller must not throw on out-of-range. */
  next(): Promise<void>;
  prev(): Promise<void>;
  goToPage(n: number): Promise<void>;
  /** EPUB: jumps to the CFI range. PDF/CBZ: jumps to recorded page. */
  goToHighlight(highlight: Highlight): Promise<void>;

  /** Jump into the table of contents (EPUB only — other controllers
   *  resolve this as a no-op so the toolbar can call it unconditionally). */
  goToToc(href: string): Promise<void>;

  /** Highlights. createHighlight() returns a draft ready for
   *  `highlightsApi.create()`, or null when no selection. The
   *  orchestrator is responsible for the HTTP POST and for calling
   *  applyHighlights with the saved row once the API responds. */
  createHighlight(color?: string): Promise<HighlightDraft | null>;
  /** deleteHighlight is a no-op on the controller — the orchestrator
   *  calls `highlightsApi.delete(id)` and re-passes the surviving list
   *  to `applyHighlights`. */
  deleteHighlight(id: number): Promise<void>;
  /** Returns the highlights the controller knows about (the
   *  orchestrator's source of truth). */
  getHighlights(): Promise<Highlight[]>;

  /** Apply a remote-sourced highlight set (used after fetching the
   *  saved list from the backend on init, and after delete). */
  applyHighlights(highlights: Highlight[]): void;

  /** Reader theme + typography. PDF/CBZ ignore fontSize/fontFamily. */
  setFontSize(rem: number): void;
  setFontFamily(family: 'serif' | 'sans'): void;
  setLineHeight(value: number): void;
  setTheme(theme: 'light' | 'sepia' | 'dark'): void;

  /** Pub/sub. Returns an unsubscribe function — exactly the
   *  shape addEventListener promises, so the call site is symmetric. */
  on<E extends ReaderEvent>(event: E, cb: ReaderEventMap[E]): () => void;
}

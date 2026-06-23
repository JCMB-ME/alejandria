/**
 * ReaderController factory (Phase D, item D8).
 *
 * The page calls `createControllerFor(bookFormat.type)` after
 * `bookFormat` resolves. This factory is the ONLY place that imports
 * the concrete controller classes — everything else speaks
 * `ReaderController`.
 */
import type { BookFormatType, ReaderController } from './types';
import { EpubController } from './EpubController.svelte';
import { PdfController } from './PdfController.svelte';
import { CbzController } from './CbzController.svelte';
import { TextController } from './TextController.svelte';

export function createControllerFor(format: BookFormatType): ReaderController {
  switch (format) {
    case 'epub': return new EpubController();
    case 'pdf':  return new PdfController();
    case 'cbz':  return new CbzController();
    case 'fb2':
    case 'rtf':
    case 'txt':  return new TextController();
  }
}

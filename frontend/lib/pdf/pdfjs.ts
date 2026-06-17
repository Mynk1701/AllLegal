// Single entry point for pdfjs-dist. We use the LEGACY build: the v6 main build
// calls Map.prototype.getOrInsertComputed (a bleeding-edge proposal no current
// browser implements), which throws at render time; the legacy build ships the
// polyfills. Both the main-thread module AND the worker must be legacy, so
// public/pdf.worker.min.mjs is copied from legacy/build too, version-matched.
//
// Only imported by client components that are themselves dynamically loaded with
// { ssr: false }, so pdfjs never runs during SSR/prerender. The window guard is
// belt-and-braces.

import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf.mjs';

if (typeof window !== 'undefined' && !pdfjsLib.GlobalWorkerOptions.workerSrc) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';
}

export { pdfjsLib };
export type { PDFDocumentProxy, PDFPageProxy, PageViewport } from 'pdfjs-dist';

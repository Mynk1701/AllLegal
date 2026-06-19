'use client';

// Owns the pdfjs document lifecycle for one case: fetch the signed-URL bytes once
// into an ArrayBuffer, open the doc, estimate page size (from page 1) for
// virtualization reserve, group every chunk's rects by page, render a PdfPage per
// page, and scroll the active (matched) chunk into view on load.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { pdfjsLib, type PDFDocumentProxy } from '@/lib/pdf/pdfjs';
import type { HoverInfo, PageChunk, ReaderChunk } from '@/lib/reader/types';
import type { Annotation, AnnotationDraft } from '@/lib/groups/types';
import PdfPage from './PdfPage';

interface Props {
  pdfUrl: string;
  chunks: ReaderChunk[];
  activeChunkId: string | null;
  scale: number;
  onHover: (info: HoverInfo | null) => void;
  hoveredChunkId: string | null;
  annotations: Annotation[];
  annotateEnabled: boolean;
  showHighlights: boolean;
  onCreateAnnotation: (draft: AnnotationDraft) => void;
  onDeleteAnnotation: (id: string) => void;
}

export default function PdfDocument({
  pdfUrl,
  chunks,
  activeChunkId,
  scale,
  onHover,
  hoveredChunkId,
  annotations,
  annotateEnabled,
  showHighlights,
  onCreateAnnotation,
  onDeleteAnnotation,
}: Props) {
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [estimate, setEstimate] = useState<{ w: number; h: number }>({ w: 612, h: 792 });
  const [error, setError] = useState<string | null>(null);
  const pageEls = useRef<Map<number, HTMLDivElement>>(new Map());

  // Load the document. Bytes fetched into an ArrayBuffer so a mid-read signed-URL
  // expiry can't break rendering (PDF.js holds the bytes).
  useEffect(() => {
    let cancelled = false;
    // The loading task (not the document proxy) owns destroy() in pdfjs v6;
    // destroying it tears down the document + worker transport on cleanup.
    let task: ReturnType<typeof pdfjsLib.getDocument> | null = null;
    (async () => {
      try {
        const res = await fetch(pdfUrl);
        if (!res.ok) throw new Error(`PDF fetch failed (${res.status})`);
        const data = await res.arrayBuffer();
        if (cancelled) return;
        task = pdfjsLib.getDocument({ data });
        const doc = await task.promise;
        if (cancelled) return;
        const page1 = await doc.getPage(1);
        const vp = page1.getViewport({ scale });
        if (cancelled) return;
        setEstimate({ w: vp.width, h: vp.height });
        setPdf(doc);
        setNumPages(doc.numPages);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load PDF');
      }
    })();
    return () => {
      cancelled = true;
      task?.destroy();
    };
    // scale intentionally excluded: reloading the doc on zoom is wasteful; the
    // estimate only seeds the reserve and pages re-render on scale themselves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pdfUrl]);

  // Group each chunk's rects by page → per-page draw + hit-test payload.
  const chunksByPage = useMemo(() => {
    const map = new Map<number, PageChunk[]>();
    for (const c of chunks) {
      if (!c.bbox) continue;
      const byPage = new Map<number, [number, number, number, number][]>();
      for (const { page, rect } of c.bbox) {
        if (!byPage.has(page)) byPage.set(page, []);
        byPage.get(page)!.push(rect);
      }
      for (const [page, rects] of byPage) {
        if (!map.has(page)) map.set(page, []);
        map.get(page)!.push({ chunkId: c.chunk_id, chunkType: c.chunk_type, rects });
      }
    }
    return map;
  }, [chunks]);

  // An annotation appears on every page its rects touch (multi-page is rare).
  const annotationsByPage = useMemo(() => {
    const map = new Map<number, Annotation[]>();
    for (const a of annotations) {
      for (const page of new Set(a.rects.map((r) => r.page))) {
        if (!map.has(page)) map.set(page, []);
        map.get(page)!.push(a);
      }
    }
    return map;
  }, [annotations]);

  const registerEl = useCallback((pageNumber: number, el: HTMLDivElement | null) => {
    if (el) pageEls.current.set(pageNumber, el);
    else pageEls.current.delete(pageNumber);
  }, []);

  // Scroll the active chunk's first page into view once the doc is ready.
  useEffect(() => {
    if (!pdf || !activeChunkId) return;
    const active = chunks.find((c) => c.chunk_id === activeChunkId);
    const firstPage = active?.bbox?.[0]?.page ?? active?.page_range?.[0];
    if (!firstPage) return;
    const t = setTimeout(() => {
      pageEls.current.get(firstPage)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 120);
    return () => clearTimeout(t);
  }, [pdf, activeChunkId, chunks]);

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-10 text-center text-sm font-semibold text-rose-600">
        Couldn’t load the PDF: {error}
      </div>
    );
  }
  if (!pdf) {
    return (
      <div className="flex h-full items-center justify-center p-10 text-sm font-semibold text-slate-400">
        Loading judgment…
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-6 py-8">
      {Array.from({ length: numPages }, (_, i) => i + 1).map((n) => (
        <PdfPage
          key={n}
          pdf={pdf}
          pageNumber={n}
          scale={scale}
          estimatedWidth={estimate.w}
          estimatedHeight={estimate.h}
          pageChunks={chunksByPage.get(n) ?? []}
          activeChunkId={activeChunkId}
          hoveredChunkId={hoveredChunkId}
          onHover={onHover}
          registerEl={registerEl}
          pageAnnotations={annotationsByPage.get(n) ?? []}
          annotateEnabled={annotateEnabled}
          showHighlights={showHighlights}
          onCreateAnnotation={onCreateAnnotation}
          onDeleteAnnotation={onDeleteAnnotation}
        />
      ))}
    </div>
  );
}

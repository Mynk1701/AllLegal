'use client';

// One PDF page: a <canvas> + a highlight overlay. Virtualized — the wrapper is
// reserved at an estimated size immediately (so total scroll height and
// scroll-to are correct), but we only call getPage()/render() once the page
// nears the viewport (IntersectionObserver). Once known, the wrapper is set to
// the page's exact viewport size so canvas and overlay always line up.

import { useEffect, useMemo, useRef, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { clientRectToNativeRect, nativeRectToOverlay, pointInBox, type OverlayBox } from '@/lib/pdf/coords';
import { pdfjsLib, type PDFDocumentProxy, type PageViewport } from '@/lib/pdf/pdfjs';
import type { HoverInfo, PageChunk } from '@/lib/reader/types';
import type { Annotation, AnnotationDraft } from '@/lib/groups/types';
import HighlightOverlay from './HighlightOverlay';
import AnnotationLayer from './AnnotationLayer';
import SelectionToolbar from './SelectionToolbar';

type Rect = [number, number, number, number];

interface Props {
  pdf: PDFDocumentProxy;
  pageNumber: number;
  scale: number;
  estimatedWidth: number;
  estimatedHeight: number;
  pageChunks: PageChunk[];
  activeChunkId: string | null;
  hoveredChunkId: string | null;
  onHover: (info: HoverInfo | null) => void;
  registerEl: (pageNumber: number, el: HTMLDivElement | null) => void;
  pageAnnotations: Annotation[];
  annotateEnabled: boolean;
  showHighlights: boolean;
  onCreateAnnotation: (draft: AnnotationDraft) => void;
  onDeleteAnnotation: (id: string) => void;
}

export default function PdfPage({
  pdf,
  pageNumber,
  scale,
  estimatedWidth,
  estimatedHeight,
  pageChunks,
  activeChunkId,
  hoveredChunkId,
  onHover,
  registerEl,
  pageAnnotations,
  annotateEnabled,
  showHighlights,
  onCreateAnnotation,
  onDeleteAnnotation,
}: Props) {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const textLayerRef = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const [viewport, setViewport] = useState<PageViewport | null>(null);
  const [pendingSel, setPendingSel] = useState<
    { rects: { page: number; rect: Rect }[]; anchor: { left: number; top: number } } | null
  >(null);
  const [selectedAnnId, setSelectedAnnId] = useState<string | null>(null);

  // Reserve the page well before it scrolls in, so render feels instant.
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) setVisible(true);
      },
      { rootMargin: '800px 0px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // Render the page to canvas once visible (and re-render on scale change).
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    let renderTask: { promise: Promise<void>; cancel: () => void } | null = null;
    let textLayer: { render: () => Promise<unknown>; cancel: () => void } | null = null;

    (async () => {
      const page = await pdf.getPage(pageNumber);
      if (cancelled) return;
      const vp = page.getViewport({ scale });
      setViewport(vp);

      const canvas = canvasRef.current;
      if (!canvas) return;

      // Crisp on hi-dpi: back the canvas at scale*dpr, but keep CSS size at the
      // scale-only viewport so overlay/hit-test math stays dpr-independent.
      const dpr = window.devicePixelRatio || 1;
      const renderVp = page.getViewport({ scale: scale * dpr });
      canvas.width = Math.floor(renderVp.width);
      canvas.height = Math.floor(renderVp.height);
      canvas.style.width = `${Math.floor(vp.width)}px`;
      canvas.style.height = `${Math.floor(vp.height)}px`;

      // pdfjs v6: pass the canvas element; it derives the 2D context itself.
      renderTask = page.render({ canvas, viewport: renderVp });
      try {
        await renderTask.promise;
      } catch {
        // render cancelled (unmount / scale change / React strict double-invoke)
      }
      if (cancelled) return;

      // Selectable text layer over the canvas: transparent glyphs laid out to
      // match the render, so a user can select text for annotation capture.
      // Rendered at the scale-only viewport; --total-scale-factor (= scale) sizes
      // the glyph CSS (see .textLayer rules in globals.css).
      const textDiv = textLayerRef.current;
      if (textDiv) {
        textDiv.replaceChildren();
        textDiv.style.setProperty('--total-scale-factor', String(scale));
        textLayer = new pdfjsLib.TextLayer({
          textContentSource: page.streamTextContent(),
          container: textDiv,
          viewport: vp,
        });
        try {
          await textLayer.render();
        } catch {
          // text-layer render cancelled
        }
      }
    })();

    return () => {
      cancelled = true;
      renderTask?.cancel();
      textLayer?.cancel();
    };
  }, [pdf, pageNumber, scale, visible]);

  // Precompute screen-space boxes once per (chunks, viewport) for fast hover.
  const hitIndex = useMemo(() => {
    if (!viewport) return [] as { chunkId: string; chunkType?: string | null; box: OverlayBox }[];
    const out: { chunkId: string; chunkType?: string | null; box: OverlayBox }[] = [];
    for (const pc of pageChunks) {
      for (const r of pc.rects) {
        out.push({ chunkId: pc.chunkId, chunkType: pc.chunkType, box: nativeRectToOverlay(r, viewport) });
      }
    }
    return out;
  }, [pageChunks, viewport]);

  const rafRef = useRef<number | null>(null);
  const handleMove = (e: React.MouseEvent) => {
    if (!showHighlights) return;
    const el = wrapperRef.current;
    if (!el || hitIndex.length === 0) return;
    const rect = el.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const cx = e.clientX;
    const cy = e.clientY;
    if (rafRef.current != null) return; // throttle to one hit-test per frame
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      const hit = hitIndex.find((h) => pointInBox(px, py, h.box));
      onHover(hit ? { chunkId: hit.chunkId, chunkType: hit.chunkType, x: cx, y: cy } : null);
    });
  };

  // ----- annotations: click hit-test + text-selection capture -----
  const annHitIndex = useMemo(() => {
    if (!viewport) return [] as { id: string; box: OverlayBox }[];
    const out: { id: string; box: OverlayBox }[] = [];
    for (const a of pageAnnotations) {
      for (const r of a.rects) {
        if (r.page === pageNumber) out.push({ id: a.id, box: nativeRectToOverlay(r.rect, viewport) });
      }
    }
    return out;
  }, [pageAnnotations, viewport, pageNumber]);

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!viewport || !annotateEnabled) return;
    const wrapper = wrapperRef.current;
    if (!wrapper) return;
    const pageRect = wrapper.getBoundingClientRect();
    const sel = window.getSelection();

    // A non-collapsed selection -> capture its rects on THIS page and show the toolbar.
    if (sel && !sel.isCollapsed && sel.rangeCount > 0) {
      const clientRects = Array.from(sel.getRangeAt(0).getClientRects()).filter(
        (r) =>
          r.width > 0 &&
          r.height > 0 &&
          r.left >= pageRect.left - 1 &&
          r.right <= pageRect.right + 1 &&
          r.top >= pageRect.top - 1 &&
          r.bottom <= pageRect.bottom + 1,
      );
      if (clientRects.length === 0) {
        setPendingSel(null);
        return;
      }
      const rects = clientRects.map((r) => ({
        page: pageNumber,
        rect: clientRectToNativeRect(r, pageRect, viewport),
      }));
      const left = Math.min(...clientRects.map((r) => r.left - pageRect.left));
      const top = Math.min(...clientRects.map((r) => r.top - pageRect.top));
      setSelectedAnnId(null);
      setPendingSel({ rects, anchor: { left, top } });
      return;
    }

    // A plain click -> hit-test annotations (open its menu) or clear.
    setPendingSel(null);
    const px = e.clientX - pageRect.left;
    const py = e.clientY - pageRect.top;
    const hit = annHitIndex.find((h) => pointInBox(px, py, h.box));
    setSelectedAnnId(hit ? hit.id : null);
  };

  const handlePick = (type: Annotation['type'], color: string, comment?: string) => {
    if (!pendingSel) return;
    onCreateAnnotation({ type, color, comment, rects: pendingSel.rects });
    window.getSelection()?.removeAllRanges();
    setPendingSel(null);
  };

  const selectedAnn = useMemo(
    () => pageAnnotations.find((a) => a.id === selectedAnnId) ?? null,
    [pageAnnotations, selectedAnnId],
  );
  const menuAnchor = useMemo(() => {
    if (!selectedAnn || !viewport) return null;
    const r = selectedAnn.rects.find((x) => x.page === pageNumber);
    if (!r) return null;
    const b = nativeRectToOverlay(r.rect, viewport);
    return { left: b.left, top: b.top };
  }, [selectedAnn, viewport, pageNumber]);

  const activeRects: Rect[] = useMemo(
    () => pageChunks.filter((pc) => pc.chunkId === activeChunkId).flatMap((pc) => pc.rects),
    [pageChunks, activeChunkId],
  );
  const hoveredRects: Rect[] = useMemo(
    () =>
      hoveredChunkId && hoveredChunkId !== activeChunkId
        ? pageChunks.filter((pc) => pc.chunkId === hoveredChunkId).flatMap((pc) => pc.rects)
        : [],
    [pageChunks, hoveredChunkId, activeChunkId],
  );

  const width = viewport ? viewport.width : estimatedWidth;
  const height = viewport ? viewport.height : estimatedHeight;

  return (
    <div
      ref={(el) => {
        wrapperRef.current = el;
        registerEl(pageNumber, el);
      }}
      data-page={pageNumber}
      onMouseMove={handleMove}
      onMouseLeave={() => onHover(null)}
      onMouseUp={handleMouseUp}
      className="relative mx-auto bg-white shadow-md ring-1 ring-slate-200"
      style={{ width, height }}
    >
      <canvas ref={canvasRef} className="block" />
      <div ref={textLayerRef} className="textLayer" />
      {viewport && showHighlights && (
        <HighlightOverlay viewport={viewport} activeRects={activeRects} hoveredRects={hoveredRects} />
      )}
      {viewport && (
        <AnnotationLayer
          viewport={viewport}
          annotations={pageAnnotations}
          pageNumber={pageNumber}
          selectedId={selectedAnnId}
        />
      )}
      {pendingSel && (
        <SelectionToolbar anchor={pendingSel.anchor} onPick={handlePick} onClose={() => setPendingSel(null)} />
      )}
      {selectedAnn && menuAnchor && (
        <div
          className="absolute z-30 flex max-w-[220px] items-center gap-2 rounded-lg border border-slate-200 bg-white px-2 py-1.5 shadow-lg"
          style={{ left: menuAnchor.left, top: Math.max(2, menuAnchor.top - 40) }}
          onMouseDown={(e) => e.stopPropagation()}
          onMouseUp={(e) => e.stopPropagation()}
        >
          {selectedAnn.comment && (
            <span className="truncate text-xs text-slate-600">{selectedAnn.comment}</span>
          )}
          <button
            onClick={() => {
              onDeleteAnnotation(selectedAnn.id);
              setSelectedAnnId(null);
            }}
            className="flex items-center gap-1 rounded-md px-1.5 py-1 text-xs font-bold text-rose-600 hover:bg-rose-50"
            title="Delete annotation"
          >
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </button>
        </div>
      )}
      {!visible && (
        <div className="absolute inset-0 flex items-center justify-center text-[11px] font-semibold text-slate-300">
          Page {pageNumber}
        </div>
      )}
    </div>
  );
}

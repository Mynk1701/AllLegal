'use client';

// One PDF page: a <canvas> + a highlight overlay. Virtualized — the wrapper is
// reserved at an estimated size immediately (so total scroll height and
// scroll-to are correct), but we only call getPage()/render() once the page
// nears the viewport (IntersectionObserver). Once known, the wrapper is set to
// the page's exact viewport size so canvas and overlay always line up.

import { useEffect, useMemo, useRef, useState } from 'react';
import { nativeRectToOverlay, pointInBox, type OverlayBox } from '@/lib/pdf/coords';
import type { PDFDocumentProxy, PageViewport } from '@/lib/pdf/pdfjs';
import type { HoverInfo, PageChunk } from '@/lib/reader/types';
import HighlightOverlay from './HighlightOverlay';

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
}: Props) {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [visible, setVisible] = useState(false);
  const [viewport, setViewport] = useState<PageViewport | null>(null);

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
    })();

    return () => {
      cancelled = true;
      renderTask?.cancel();
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
      className="relative mx-auto bg-white shadow-md ring-1 ring-slate-200"
      style={{ width, height }}
    >
      <canvas ref={canvasRef} className="block" />
      {viewport && <HighlightOverlay viewport={viewport} activeRects={activeRects} hoveredRects={hoveredRects} />}
      {!visible && (
        <div className="absolute inset-0 flex items-center justify-center text-[11px] font-semibold text-slate-300">
          Page {pageNumber}
        </div>
      )}
    </div>
  );
}

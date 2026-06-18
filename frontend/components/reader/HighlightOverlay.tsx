'use client';

// Presentational overlay for ONE page. Draws two read-only highlight layers from
// native rects, converting through this page's viewport:
//   (a) the system matched-chunk highlight (amber) — the one scrolled to,
//   (b) the currently-hovered chunk (blue) — transient, follows the cursor.
// User annotations will be a third layer here in Phase 2. All boxes are
// pointer-events-none so they never eat the text-layer selection / hover.

import { nativeRectToOverlay } from '@/lib/pdf/coords';
import type { PageViewport } from '@/lib/pdf/pdfjs';

type Rect = [number, number, number, number];

export default function HighlightOverlay({
  viewport,
  activeRects,
  hoveredRects,
}: {
  viewport: PageViewport;
  activeRects: Rect[];
  hoveredRects: Rect[];
}) {
  return (
    <div className="pointer-events-none absolute inset-0">
      {activeRects.map((r, i) => {
        const b = nativeRectToOverlay(r, viewport);
        return (
          <div
            key={`a-${i}`}
            className="absolute rounded-sm bg-amber-300/35 ring-1 ring-amber-500/50"
            style={{ left: b.left, top: b.top, width: b.width, height: b.height }}
          />
        );
      })}
      {hoveredRects.map((r, i) => {
        const b = nativeRectToOverlay(r, viewport);
        return (
          <div
            key={`h-${i}`}
            className="absolute rounded-sm bg-blue-400/20 ring-1 ring-blue-500/40"
            style={{ left: b.left, top: b.top, width: b.width, height: b.height }}
          />
        );
      })}
    </div>
  );
}

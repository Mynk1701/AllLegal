'use client';

// User annotations for ONE page — the interactive 3rd layer the reader
// anticipated. Visuals only and pointer-events-none, so text selection (and the
// system highlight hover) underneath always works; clicks are hit-tested
// geometrically in PdfPage (same pattern as chunk hover). highlight = filled
// box, underline = bottom-edge line, note = a small marker on its first rect.

import { nativeRectToOverlay } from '@/lib/pdf/coords';
import type { PageViewport } from '@/lib/pdf/pdfjs';
import type { Annotation } from '@/lib/groups/types';

const DEFAULT_COLOR = '#FFD54A';

/** #RRGGBB -> rgba-ish via 8-digit hex; passthrough if already non-#RRGGBB. */
function withAlpha(hex: string, aa: string): string {
  return /^#[0-9a-fA-F]{6}$/.test(hex) ? `${hex}${aa}` : hex;
}

export default function AnnotationLayer({
  viewport,
  annotations,
  pageNumber,
  selectedId,
}: {
  viewport: PageViewport;
  annotations: Annotation[];
  pageNumber: number;
  selectedId: string | null;
}) {
  return (
    <div className="pointer-events-none absolute inset-0">
      {annotations.flatMap((a) => {
        const color = a.color || DEFAULT_COLOR;
        const selected = a.id === selectedId;
        const rects = a.rects.filter((r) => r.page === pageNumber);

        if (a.type === 'note') {
          const first = rects[0];
          if (!first) return [];
          const b = nativeRectToOverlay(first.rect, viewport);
          return [
            <div
              key={`${a.id}-note`}
              title={a.comment ?? 'Note'}
              className="absolute flex h-4 w-4 -translate-y-1/2 items-center justify-center rounded-full text-[10px] leading-none text-white shadow"
              style={{
                left: b.left - 6,
                top: b.top,
                backgroundColor: color,
                outline: selected ? `2px solid ${color}` : undefined,
              }}
            >
              ✎
            </div>,
          ];
        }

        return rects.map((r, i) => {
          const b = nativeRectToOverlay(r.rect, viewport);
          if (a.type === 'underline') {
            return (
              <div
                key={`${a.id}-${i}`}
                className="absolute"
                style={{
                  left: b.left,
                  top: b.top + b.height - 2,
                  width: b.width,
                  height: 2,
                  backgroundColor: color,
                  boxShadow: selected ? `0 0 0 1px ${color}` : undefined,
                }}
              />
            );
          }
          // highlight
          return (
            <div
              key={`${a.id}-${i}`}
              className="absolute rounded-[2px]"
              style={{
                left: b.left,
                top: b.top,
                width: b.width,
                height: b.height,
                backgroundColor: withAlpha(color, '59'),
                outline: selected ? `1.5px solid ${color}` : undefined,
              }}
            />
          );
        });
      })}
    </div>
  );
}

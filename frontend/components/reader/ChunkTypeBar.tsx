'use client';

// Floating bar that follows the cursor and names the chunk type of the paragraph
// under it (Fact / Ratio Decidendi / Final Order / ...). Driven purely by hover
// hit-testing in PdfPage — it never touches persisted data.

import { roleBadgeClass, roleLabel } from '@/lib/reader/roles';
import type { HoverInfo } from '@/lib/reader/types';

export default function ChunkTypeBar({ hover }: { hover: HoverInfo | null }) {
  if (!hover) return null;
  return (
    <div
      className="pointer-events-none fixed z-50"
      style={{ left: hover.x + 14, top: hover.y + 14 }}
    >
      <span
        className={`inline-block rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[0.1em] shadow-lg ring-1 ${roleBadgeClass(
          hover.chunkType,
        )}`}
      >
        {roleLabel(hover.chunkType)}
      </span>
    </div>
  );
}

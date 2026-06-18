'use client';

// Reader shell: top toolbar (title + zoom), the scrollable PDF column, and the
// metadata panel. Owns view state — zoom scale and the hovered chunk (so the
// floating ChunkTypeBar and the in-canvas hover highlight stay in sync). This is
// the component the route dynamically imports with { ssr: false }.

import { useState } from 'react';
import { ArrowLeft, Scale, ZoomIn, ZoomOut } from 'lucide-react';
import type { CaseDetail, HoverInfo } from '@/lib/reader/types';
import PdfDocument from './PdfDocument';
import MetadataPanel from './MetadataPanel';
import ChunkTypeBar from './ChunkTypeBar';

const MIN_SCALE = 0.6;
const MAX_SCALE = 2.4;
const STEP = 0.2;

export default function ReaderView({
  caseDetail,
  activeChunkId,
}: {
  caseDetail: CaseDetail;
  activeChunkId: string | null;
}) {
  const [scale, setScale] = useState(1.3);
  const [hover, setHover] = useState<HoverInfo | null>(null);

  const zoom = (delta: number) => setScale((s) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, +(s + delta).toFixed(2))));

  return (
    <div className="flex h-screen flex-col bg-slate-100">
      {/* Toolbar */}
      <header className="z-20 flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-5 py-3 shadow-sm">
        <div className="flex min-w-0 items-center gap-3">
          <button
            onClick={() => window.close()}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Close
          </button>
          <div className="flex items-center gap-2 truncate">
            <Scale className="h-4 w-4 shrink-0 text-blue-600" />
            <span className="truncate text-sm font-extrabold text-slate-900">{caseDetail.case_name}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={() => zoom(-STEP)} className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition-colors hover:bg-slate-50" aria-label="Zoom out">
            <ZoomOut className="h-4 w-4" />
          </button>
          <span className="w-12 text-center text-xs font-bold tabular-nums text-slate-500">{Math.round(scale * 100)}%</span>
          <button onClick={() => zoom(STEP)} className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition-colors hover:bg-slate-50" aria-label="Zoom in">
            <ZoomIn className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* Body */}
      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1 overflow-y-auto">
          {caseDetail.pdf_url ? (
            <PdfDocument
              pdfUrl={caseDetail.pdf_url}
              chunks={caseDetail.chunks}
              activeChunkId={activeChunkId}
              scale={scale}
              onHover={setHover}
              hoveredChunkId={hover?.chunkId ?? null}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm font-semibold text-slate-400">No PDF available for this case.</div>
          )}
        </main>
        <aside className="hidden w-[380px] shrink-0 border-l border-slate-200 lg:block">
          <MetadataPanel caseDetail={caseDetail} />
        </aside>
      </div>

      <ChunkTypeBar hover={hover} />
    </div>
  );
}

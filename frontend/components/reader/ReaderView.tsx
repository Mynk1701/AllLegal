'use client';

// Reader shell: top toolbar (title + zoom), the scrollable PDF column, and the
// metadata panel. Owns view state — zoom scale and the hovered chunk (so the
// floating ChunkTypeBar and the in-canvas hover highlight stay in sync). This is
// the component the route dynamically imports with { ssr: false }.

import { useState } from 'react';
import { ArrowLeft, Eye, EyeOff, FolderPlus, Pencil, Scale, ZoomIn, ZoomOut } from 'lucide-react';
import type { CaseDetail, HoverInfo } from '@/lib/reader/types';
import type { Annotation, AnnotationDraft } from '@/lib/groups/types';
import PdfDocument from './PdfDocument';
import MetadataPanel from './MetadataPanel';
import ChunkTypeBar from './ChunkTypeBar';
import GroupPicker from '@/components/groups/GroupPicker';

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
  // Chunk 4: annotations live in local state only (no persistence yet). Chunk 6
  // replaces this with group-scoped load/auto-save via the API.
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [showHighlights, setShowHighlights] = useState(true);
  const toggleHighlights = () => {
    setShowHighlights((v) => !v);
    setHover(null); // drop any lingering hover when highlights are hidden
  };

  const handleCreateAnnotation = (draft: AnnotationDraft) => {
    setAnnotations((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        group_id: 'local',
        case_id: caseDetail.case_id,
        type: draft.type,
        rects: draft.rects,
        color: draft.color,
        comment: draft.comment ?? null,
      },
    ]);
  };
  const handleDeleteAnnotation = (id: string) =>
    setAnnotations((prev) => prev.filter((a) => a.id !== id));

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
          <button
            onClick={() => setEditMode((v) => !v)}
            title={editMode ? 'Editing on — select text to annotate' : 'Turn on annotation editing'}
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-bold transition-colors ${
              editMode
                ? 'border-blue-600 bg-blue-600 text-white'
                : 'border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Pencil className="h-3.5 w-3.5" /> {editMode ? 'Editing' : 'Edit'}
          </button>
          <button
            onClick={toggleHighlights}
            title={showHighlights ? 'Hide matched highlights & hover' : 'Show matched highlights & hover'}
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-bold transition-colors ${
              showHighlights
                ? 'border-slate-200 text-slate-600 hover:bg-slate-50'
                : 'border-amber-300 bg-amber-50 text-amber-700'
            }`}
          >
            {showHighlights ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />} Highlights
          </button>
          <span className="mx-1 h-5 w-px bg-slate-200" />
          <button
            onClick={() => setPickerOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50"
          >
            <FolderPlus className="h-3.5 w-3.5" /> Add to group
          </button>
          <span className="mx-1 h-5 w-px bg-slate-200" />
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
              annotations={annotations}
              annotateEnabled={editMode}
              showHighlights={showHighlights}
              onCreateAnnotation={handleCreateAnnotation}
              onDeleteAnnotation={handleDeleteAnnotation}
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
      {pickerOpen && (
        <GroupPicker
          caseId={caseDetail.case_id}
          caseName={caseDetail.case_name}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  );
}

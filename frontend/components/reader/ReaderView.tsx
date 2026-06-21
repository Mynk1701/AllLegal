'use client';

// Reader shell: top toolbar (title + active-group + zoom), the scrollable PDF
// column, and the metadata panel. Owns view state (zoom, hovered chunk) AND the
// annotation layer, which is GROUP-SCOPED: annotations are keyed by (group, case),
// so the reader works against one "active" group at a time — loading that group's
// saved annotations and persisting new ones to it via the API. Reading needs no
// group; annotating requires an active group (the case must belong to one).

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Download, Eye, EyeOff, Loader2, Pencil, Scale, ZoomIn, ZoomOut } from 'lucide-react';
import {
  addCaseToGroup,
  createAnnotation,
  deleteAnnotation,
  listAnnotations,
  listGroups,
} from '@/lib/api';
import type { CaseDetail, HoverInfo } from '@/lib/reader/types';
import type { Annotation, AnnotationDraft, Group } from '@/lib/groups/types';
import { buildAnnotatedPdf } from '@/lib/pdf/exportAnnotated';
import PdfDocument from './PdfDocument';
import MetadataPanel from './MetadataPanel';
import ChunkTypeBar from './ChunkTypeBar';
import ReaderGroupControl from './ReaderGroupControl';

const MIN_SCALE = 0.6;
const MAX_SCALE = 2.4;
const STEP = 0.2;

// case_name → a filesystem-safe download filename (spaces/punctuation → "_").
const safeFilename = (name: string) =>
  name.replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 120) || 'case';

export default function ReaderView({
  caseDetail,
  activeChunkId,
  initialGroupId,
}: {
  caseDetail: CaseDetail;
  activeChunkId: string | null;
  initialGroupId: string | null;
}) {
  const router = useRouter();
  const caseId = caseDetail.case_id;

  const [scale, setScale] = useState(1.3);
  const [hover, setHover] = useState<HoverInfo | null>(null);
  const [showHighlights, setShowHighlights] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Group context. `groups` = the user's groups, each flagged has_case for THIS
  // case (so we know its memberships); `activeGroupId` = the group whose
  // annotations the reader shows/edits (null = read-only).
  const [groups, setGroups] = useState<Group[]>([]);
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);

  // Load this case's group memberships once; resolve the initial active group
  // from ?group (only if it's one of the user's groups). No silent default — a
  // case opened from search (no ?group) stays read-only until a group is picked.
  useEffect(() => {
    let cancelled = false;
    listGroups(caseId)
      .then((gs) => {
        if (cancelled) return;
        setGroups(gs);
        if (initialGroupId && gs.some((g) => g.id === initialGroupId)) {
          setActiveGroupId(initialGroupId);
        }
      })
      .catch(() => !cancelled && setGroups([]));
    return () => {
      cancelled = true;
    };
  }, [caseId, initialGroupId]);

  // Load the active group's saved annotations (and reload on switch). No active
  // group → nothing to show.
  useEffect(() => {
    if (!activeGroupId) {
      setAnnotations([]);
      return;
    }
    let cancelled = false;
    listAnnotations(activeGroupId, caseId)
      .then((rows) => !cancelled && setAnnotations(rows))
      .catch(() => !cancelled && setAnnotations([]));
    return () => {
      cancelled = true;
    };
  }, [activeGroupId, caseId]);

  // Activating a group guarantees the case is actually in it (idempotent) —
  // covers a stale ?group link or any non-membership activation, so an annotated
  // case always appears under its group.
  useEffect(() => {
    if (!activeGroupId) return;
    const g = groups.find((x) => x.id === activeGroupId);
    if (g && !g.has_case) {
      addCaseToGroup(activeGroupId, caseId)
        .then(() =>
          setGroups((prev) =>
            prev.map((x) => (x.id === activeGroupId ? { ...x, has_case: true } : x)),
          ),
        )
        .catch(() => {});
    }
  }, [activeGroupId, groups, caseId]);

  // Switch the active group + keep the URL in sync so a refresh/bookmark stays put.
  const selectGroup = (groupId: string) => {
    setActiveGroupId(groupId);
    const params = new URLSearchParams();
    params.set('group', groupId);
    if (activeChunkId) params.set('chunk', activeChunkId);
    router.replace(`/reader/${encodeURIComponent(caseId)}?${params.toString()}`, { scroll: false });
  };

  // After GroupPicker adds the case to a group, mark it a member, refresh
  // memberships, and make it active so new annotations land there.
  const handleAddedToGroup = (groupId: string) => {
    setGroups((prev) =>
      prev.some((g) => g.id === groupId)
        ? prev.map((g) => (g.id === groupId ? { ...g, has_case: true } : g))
        : prev,
    );
    listGroups(caseId).then(setGroups).catch(() => {});
    selectGroup(groupId);
  };

  const toggleHighlights = () => {
    setShowHighlights((v) => !v);
    setHover(null); // drop any lingering hover when highlights are hidden
  };

  // Persist a new gesture to the active group (optimistic; rolled back on error).
  const handleCreateAnnotation = async (draft: AnnotationDraft) => {
    if (!activeGroupId) return; // editing is gated on an active group
    const tempId = `temp-${crypto.randomUUID()}`;
    setAnnotations((prev) => [
      ...prev,
      {
        id: tempId,
        group_id: activeGroupId,
        case_id: caseId,
        type: draft.type,
        rects: draft.rects,
        color: draft.color,
        comment: draft.comment ?? null,
      },
    ]);
    try {
      const saved = await createAnnotation(activeGroupId, {
        case_id: caseId,
        type: draft.type,
        rects: draft.rects,
        color: draft.color,
        comment: draft.comment,
      });
      setAnnotations((prev) => prev.map((a) => (a.id === tempId ? saved : a)));
    } catch {
      setAnnotations((prev) => prev.filter((a) => a.id !== tempId)); // rollback
    }
  };

  const handleDeleteAnnotation = async (id: string) => {
    if (!activeGroupId) return;
    const removed = annotations.find((a) => a.id === id);
    setAnnotations((prev) => prev.filter((a) => a.id !== id));
    if (id.startsWith('temp-')) return; // optimistic row, never persisted
    try {
      await deleteAnnotation(activeGroupId, id);
    } catch {
      if (removed) setAnnotations((prev) => [...prev, removed]); // rollback
    }
  };

  // Download the PDF with the ACTIVE group's annotations baked in: highlights/
  // underlines drawn into the page, notes as clickable PDF sticky-notes (see
  // buildAnnotatedPdf). Signed Storage URLs usually render inline, so we fetch the
  // bytes and save them under a case-named filename. With no annotations we save
  // the original bytes untouched.
  const handleDownload = async () => {
    if (!caseDetail.pdf_url || downloading) return;
    setDownloading(true);
    try {
      const res = await fetch(caseDetail.pdf_url);
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const bytes = await res.arrayBuffer();
      const out = annotations.length
        ? await buildAnnotatedPdf(bytes, annotations)
        : new Uint8Array(bytes);
      const url = URL.createObjectURL(new Blob([out as BlobPart], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `${safeFilename(caseDetail.case_name || caseId)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('PDF download failed:', e);
    } finally {
      setDownloading(false);
    }
  };

  const zoom = (delta: number) =>
    setScale((s) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, +(s + delta).toFixed(2))));

  const canEdit = !!activeGroupId;

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
            onClick={() => canEdit && setEditMode((v) => !v)}
            disabled={!canEdit}
            title={
              !canEdit
                ? 'Add this case to a group to annotate'
                : editMode
                  ? 'Editing on — select text to annotate'
                  : 'Turn on annotation editing'
            }
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
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
          <button
            onClick={handleDownload}
            disabled={!caseDetail.pdf_url || downloading}
            title={caseDetail.pdf_url ? 'Download PDF' : 'No PDF available'}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {downloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />} Download
          </button>
          <span className="mx-1 h-5 w-px bg-slate-200" />
          <ReaderGroupControl
            caseId={caseId}
            caseName={caseDetail.case_name}
            groups={groups}
            activeGroupId={activeGroupId}
            onSelect={selectGroup}
            onAdded={handleAddedToGroup}
          />
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
              annotateEnabled={editMode && canEdit}
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
    </div>
  );
}

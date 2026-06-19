'use client';

// Floating mini-toolbar shown at a text selection: Highlight / Underline / Note
// (+ colour swatches). Positioned absolutely within the page wrapper (page-local
// px). stopPropagation on mouse events keeps PdfPage's wrapper mouseup from
// treating a toolbar click as a fresh click and dismissing us.

import { useState } from 'react';
import { Highlighter, Underline, StickyNote } from 'lucide-react';
import type { AnnotationType } from '@/lib/groups/types';

export const ANNOTATION_COLORS = ['#FFD54A', '#A5D6A7', '#90CAF9', '#F48FB1'];

export default function SelectionToolbar({
  anchor,
  onPick,
  onClose,
}: {
  anchor: { left: number; top: number };
  onPick: (type: AnnotationType, color: string, comment?: string) => void;
  onClose: () => void;
}) {
  const [color, setColor] = useState(ANNOTATION_COLORS[0]);
  const [noteMode, setNoteMode] = useState(false);
  const [comment, setComment] = useState('');

  const stop = (e: React.MouseEvent) => e.stopPropagation();
  const top = Math.max(2, anchor.top - 46);

  return (
    <div
      className="absolute z-30"
      style={{ left: anchor.left, top }}
      onMouseDown={stop}
      onMouseUp={stop}
    >
      {!noteMode ? (
        <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-lg">
          <button
            onClick={() => onPick('highlight', color)}
            className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100"
            title="Highlight"
          >
            <Highlighter className="h-4 w-4" />
          </button>
          <button
            onClick={() => onPick('underline', color)}
            className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100"
            title="Underline"
          >
            <Underline className="h-4 w-4" />
          </button>
          <button
            onClick={() => setNoteMode(true)}
            className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100"
            title="Note"
          >
            <StickyNote className="h-4 w-4" />
          </button>
          <span className="mx-0.5 h-5 w-px bg-slate-200" />
          {ANNOTATION_COLORS.map((c) => (
            <button
              key={c}
              onClick={() => setColor(c)}
              className="h-5 w-5 rounded-full ring-offset-1"
              style={{ backgroundColor: c, outline: color === c ? `2px solid ${c}` : 'none' }}
              title={c}
            />
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg">
          <input
            autoFocus
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Add a note…"
            className="w-48 rounded-md border border-slate-200 px-2 py-1 text-xs outline-none focus:border-blue-400"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && comment.trim()) onPick('note', color, comment.trim());
              if (e.key === 'Escape') onClose();
            }}
          />
          <button
            onClick={() => comment.trim() && onPick('note', color, comment.trim())}
            className="rounded-md bg-blue-600 px-2.5 py-1 text-xs font-bold text-white hover:bg-blue-700"
          >
            Save
          </button>
        </div>
      )}
    </div>
  );
}

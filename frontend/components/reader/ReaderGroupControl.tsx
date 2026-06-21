'use client';

// Reader's active-group control. Reader annotations are scoped to ONE "active"
// group (annotations are keyed by group + case), so this picks which group the
// reader reads/writes annotations for:
//   • lists the groups this case is ALREADY in — click to ACTIVATE one (no new
//     membership is created), which loads that group's annotations;
//   • "Add to another group…" opens the shared GroupPicker for groups it isn't in
//     yet / creating a new one, then activates whichever was just added.
// With no active group the case is read-only (annotating is disabled upstream).

import { useState } from 'react';
import { Check, ChevronDown, FolderPlus, Plus } from 'lucide-react';
import GroupPicker from '@/components/groups/GroupPicker';
import type { Group } from '@/lib/groups/types';

export default function ReaderGroupControl({
  caseId,
  caseName,
  groups,
  activeGroupId,
  onSelect,
  onAdded,
}: {
  caseId: string;
  caseName?: string;
  groups: Group[];
  activeGroupId: string | null;
  onSelect: (groupId: string) => void;
  onAdded: (groupId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const memberships = groups.filter((g) => g.has_case);
  const active = groups.find((g) => g.id === activeGroupId) ?? null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        title={active ? `Annotating in “${active.name}”` : 'Pick a group to annotate in'}
        className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-bold transition-colors ${
          active
            ? 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100'
            : 'border-slate-200 text-slate-600 hover:bg-slate-50'
        }`}
      >
        <FolderPlus className="h-3.5 w-3.5" />
        <span className="max-w-[160px] truncate">{active ? active.name : 'Add to group'}</span>
        <ChevronDown className="h-3.5 w-3.5 opacity-60" />
      </button>

      {open && (
        <>
          {/* click-away backdrop */}
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-40 mt-1 w-60 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
            {memberships.length > 0 ? (
              <div className="max-h-64 overflow-y-auto py-1">
                <p className="px-3 py-1.5 text-[10px] font-black uppercase tracking-wider text-slate-400">
                  This case is in
                </p>
                {memberships.map((g) => (
                  <button
                    key={g.id}
                    onClick={() => {
                      onSelect(g.id);
                      setOpen(false);
                    }}
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50"
                  >
                    <span className="truncate font-medium text-slate-700">{g.name}</span>
                    {g.id === activeGroupId && <Check className="h-4 w-4 shrink-0 text-blue-600" />}
                  </button>
                ))}
              </div>
            ) : (
              <p className="px-3 py-3 text-xs font-medium text-slate-400">
                This case isn’t in any group yet.
              </p>
            )}
            <button
              onClick={() => {
                setPickerOpen(true);
                setOpen(false);
              }}
              className="flex w-full items-center gap-2 border-t border-slate-100 px-3 py-2.5 text-left text-sm font-bold text-blue-600 hover:bg-blue-50"
            >
              <Plus className="h-4 w-4" /> Add to another group…
            </button>
          </div>
        </>
      )}

      {pickerOpen && (
        <GroupPicker
          caseId={caseId}
          caseName={caseName}
          onClose={() => setPickerOpen(false)}
          onAdded={onAdded}
        />
      )}
    </div>
  );
}

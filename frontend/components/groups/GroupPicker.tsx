'use client';

// Floating "add this case to a group" picker, reused from the search detail
// panel and the reader toolbar. Lists the user's groups (add on click) and
// creates one inline (name + Create, per the agreed simple flow). Stays open so
// a case can be added to several groups; the user closes it.

import { useEffect, useState } from 'react';
import { X, Plus, Check, FolderPlus, Loader2 } from 'lucide-react';
import { addCaseToGroup, createGroup, listGroups } from '@/lib/api';
import type { Group } from '@/lib/groups/types';

export default function GroupPicker({
  caseId,
  caseName,
  onClose,
}: {
  caseId: string;
  caseName?: string;
  onClose: () => void;
}) {
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [addedTo, setAddedTo] = useState<Set<string>>(new Set());
  const [busyId, setBusyId] = useState<string | null>(null);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listGroups(caseId)
      .then((g) => {
        if (cancelled) return;
        setGroups(g);
        // Seed from server: groups already containing this case are disabled.
        setAddedTo(new Set(g.filter((x) => x.has_case).map((x) => x.id)));
      })
      .catch(() => !cancelled && setError('Failed to load groups'));
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const markAdded = (id: string) => setAddedTo((prev) => new Set(prev).add(id));

  const add = async (groupId: string) => {
    setBusyId(groupId);
    setError(null);
    try {
      await addCaseToGroup(groupId, caseId);
      markAdded(groupId);
    } catch {
      setError('Failed to add to group');
    } finally {
      setBusyId(null);
    }
  };

  const createAndAdd = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      const grp = await createGroup(name);
      await addCaseToGroup(grp.id, caseId);
      setGroups((prev) => [{ ...grp, item_count: 1 }, ...(prev ?? [])]);
      markAdded(grp.id);
      setNewName('');
    } catch {
      setError('Failed to create group');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm overflow-hidden rounded-2xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h3 className="text-sm font-bold text-slate-900">Add to group</h3>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        {caseName && <p className="truncate px-4 pt-2 text-xs font-medium text-slate-500">{caseName}</p>}

        <div className="max-h-64 overflow-y-auto px-2 py-2">
          {groups === null && !error && (
            <div className="flex items-center gap-2 px-2 py-6 text-xs font-medium text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading groups…
            </div>
          )}
          {groups && groups.length === 0 && (
            <div className="px-2 py-4 text-xs font-medium text-slate-400">No groups yet — create one below.</div>
          )}
          {groups?.map((g) => {
            const added = addedTo.has(g.id);
            return (
              <button
                key={g.id}
                disabled={added || busyId === g.id}
                onClick={() => add(g.id)}
                className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-sm hover:bg-slate-50 disabled:cursor-default"
              >
                <span className="truncate font-medium text-slate-700">{g.name}</span>
                {added ? (
                  <span className="flex shrink-0 items-center gap-1 text-xs font-bold text-green-600">
                    <Check className="h-3.5 w-3.5" /> In group
                  </span>
                ) : busyId === g.id ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-slate-400" />
                ) : (
                  <Plus className="h-4 w-4 shrink-0 text-slate-400" />
                )}
              </button>
            );
          })}
        </div>

        {error && <p className="px-4 pb-1 text-xs font-semibold text-rose-600">{error}</p>}

        <div className="flex items-center gap-2 border-t border-slate-100 px-3 py-3">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') createAndAdd();
            }}
            placeholder="New group name"
            className="min-w-0 flex-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-sm outline-none focus:border-blue-400"
          />
          <button
            onClick={createAndAdd}
            disabled={!newName.trim() || creating}
            className="flex shrink-0 items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FolderPlus className="h-3.5 w-3.5" />}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

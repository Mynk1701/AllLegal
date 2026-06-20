'use client';

// Groups landing — the screen that finally gives "Groups" a home. Lists the
// user's groups (the backend has had full CRUD all along; there was just no UI
// door) and lets them create one inline. Each card links to the group detail,
// which gets fleshed out in a later pass.

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { FolderClosed, FolderPlus, Loader2, ChevronRight } from 'lucide-react';
import { listGroups, createGroup } from '@/lib/api';
import type { Group } from '@/lib/groups/types';

export default function GroupsPage() {
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listGroups()
      .then((g) => !cancelled && setGroups(g))
      .catch(() => !cancelled && setError('Failed to load groups'));
    return () => {
      cancelled = true;
    };
  }, []);

  const create = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      const grp = await createGroup(name);
      setGroups((prev) => [{ ...grp, item_count: 0 }, ...(prev ?? [])]);
      setNewName('');
    } catch {
      setError('Failed to create group');
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto px-8 py-12">
        <div className="mb-8">
          <h1 className="text-2xl font-black tracking-tight text-slate-900">Groups</h1>
          <p className="text-sm text-slate-500 font-medium mt-1">
            Organise the cases you find into matters you can return to.
          </p>
        </div>

        {/* Create */}
        <div className="flex items-center gap-2 mb-8 max-w-md">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && create()}
            placeholder="New group name"
            className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm font-medium outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-500/10 transition-all"
          />
          <button
            onClick={create}
            disabled={!newName.trim() || creating}
            className="flex shrink-0 items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-all active:scale-95"
          >
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <FolderPlus className="h-4 w-4" />}
            Create
          </button>
        </div>

        {error && <p className="mb-4 text-sm font-semibold text-rose-600">{error}</p>}

        {/* List */}
        {groups === null && !error ? (
          <div className="flex items-center gap-2 text-sm font-medium text-slate-400 py-10">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading groups…
          </div>
        ) : groups && groups.length === 0 ? (
          <div className="text-center py-20">
            <div className="w-16 h-16 bg-slate-50 rounded-3xl flex items-center justify-center mx-auto mb-4">
              <FolderClosed className="w-7 h-7 text-slate-300" />
            </div>
            <p className="text-slate-500 font-medium">No groups yet.</p>
            <p className="text-sm text-slate-400 mt-1">Create one above, or add cases to a group from search results.</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-3">
            {groups?.map((g) => (
              <Link
                key={g.id}
                href={`/groups/${encodeURIComponent(g.id)}`}
                className="group flex items-center justify-between gap-3 p-5 rounded-2xl bg-white border border-slate-200/80 hover:border-blue-300 hover:shadow-lg hover:shadow-blue-500/5 transition-all"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0">
                    <FolderClosed className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-bold text-slate-900 truncate">{g.name}</p>
                    <p className="text-xs font-semibold text-slate-400">
                      {g.item_count} {g.item_count === 1 ? 'case' : 'cases'}
                    </p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-blue-500 group-hover:translate-x-1 transition-all shrink-0" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

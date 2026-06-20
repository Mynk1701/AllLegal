'use client';

// Sidebar Groups tree. Two levels of disclosure: groups → a group's cases. The
// group list loads when the section opens; a group's items load the first time
// it's expanded. Items carry only a case_id (the backend GroupItem has no
// case_name yet), so we fetch each case's detail to show a readable name and
// cache it. Clicking a case opens it in the reader. Styled for the dark nav rail.

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { FolderClosed, ChevronRight, Loader2, FileText } from 'lucide-react';
import { listGroups, getGroup, getCaseDetail } from '@/lib/api';
import type { Group, GroupItem } from '@/lib/groups/types';

export default function GroupsTree() {
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [error, setError] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  // undefined = never opened, null = loading, [] / list = loaded
  const [itemsByGroup, setItemsByGroup] = useState<Record<string, GroupItem[] | null | undefined>>({});
  const [names, setNames] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    listGroups()
      .then((g) => !cancelled && setGroups(g))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, []);

  const toggle = async (id: string) => {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    if (itemsByGroup[id] !== undefined) return; // already loaded/loading

    setItemsByGroup((p) => ({ ...p, [id]: null }));
    try {
      const detail = await getGroup(id);
      setItemsByGroup((p) => ({ ...p, [id]: detail.items }));
      // Resolve case names lazily (GroupItem has only case_id).
      detail.items.forEach(async (it) => {
        if (names[it.case_id] !== undefined) return;
        try {
          const c = await getCaseDetail(it.case_id);
          setNames((p) => ({ ...p, [it.case_id]: c.case_name || it.case_id }));
        } catch {
          setNames((p) => ({ ...p, [it.case_id]: it.case_id }));
        }
      });
    } catch {
      setItemsByGroup((p) => ({ ...p, [id]: [] }));
    }
  };

  if (error) {
    return <p className="px-3 py-2 text-[11px] font-semibold text-slate-500">Couldn't load groups.</p>;
  }
  if (groups === null) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-[11px] font-semibold text-slate-500">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…
      </div>
    );
  }
  if (groups.length === 0) {
    return (
      <div className="px-3 py-2">
        <p className="text-[11px] font-semibold text-slate-500">No groups yet.</p>
        <Link href="/groups" className="text-[11px] font-bold text-blue-400 hover:text-blue-300">
          Create one →
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0.5">
      {groups.map((grp) => {
        const isOpen = openId === grp.id;
        const items = itemsByGroup[grp.id];
        return (
          <div key={grp.id}>
            <button
              onClick={() => toggle(grp.id)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-slate-300 hover:bg-white/5 hover:text-white transition-colors"
            >
              <ChevronRight className={`w-3.5 h-3.5 shrink-0 text-slate-500 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
              <FolderClosed className="w-3.5 h-3.5 shrink-0 text-slate-500" />
              <span className="text-xs font-semibold truncate flex-1">{grp.name}</span>
              <span className="text-[10px] font-bold text-slate-500 shrink-0">{grp.item_count}</span>
            </button>

            {isOpen && (
              <div className="ml-4 pl-2 border-l border-white/10 flex flex-col gap-0.5 my-0.5">
                {items === null && (
                  <div className="flex items-center gap-2 px-3 py-1.5 text-[11px] font-semibold text-slate-500">
                    <Loader2 className="w-3 h-3 animate-spin" /> Loading…
                  </div>
                )}
                {items && items.length === 0 && (
                  <p className="px-3 py-1.5 text-[11px] font-semibold text-slate-500">Empty group.</p>
                )}
                {items?.map((it) => (
                  <Link
                    key={it.case_id}
                    href={`/reader/${encodeURIComponent(it.case_id)}`}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-slate-400 hover:bg-white/5 hover:text-white transition-colors"
                  >
                    <FileText className="w-3.5 h-3.5 shrink-0 text-slate-500" />
                    <span className="text-[11px] font-semibold truncate">
                      {names[it.case_id] ?? 'Loading…'}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        );
      })}
      <Link
        href="/groups"
        className="mt-1 px-3 py-2 text-[11px] font-bold text-blue-400 hover:text-blue-300 transition-colors"
      >
        Manage all groups →
      </Link>
    </div>
  );
}

'use client';

// Sidebar History tree. Mounts lazily (only when the History section is open),
// fetches recent searches, and renders each in compressed form — query text +
// "N filters". Clicking one deep-links to /search?<encoded>, where the search
// page replays it. Styled for the dark nav rail.

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Clock, Loader2 } from 'lucide-react';
import { listSearchHistory } from '@/lib/api';
import { filtersToQueryString, filterSummary, type HistoryItem } from '@/lib/search';

export default function HistoryTree() {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState(false);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    listSearchHistory()
      .then((d) => !cancelled && setItems(d))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, []);

  const open = (it: HistoryItem) => {
    const qs = filtersToQueryString(it.query || '', it.filters || {});
    router.push(`/search${qs ? `?${qs}` : ''}`);
  };

  if (error) {
    return <p className="px-3 py-2 text-[11px] font-semibold text-slate-500">Couldn't load history.</p>;
  }
  if (items === null) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-[11px] font-semibold text-slate-500">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…
      </div>
    );
  }
  if (items.length === 0) {
    return <p className="px-3 py-2 text-[11px] font-semibold text-slate-500">No searches yet.</p>;
  }

  return (
    <div className="flex flex-col gap-0.5 max-h-64 overflow-y-auto pr-0.5">
      {items.slice(0, 50).map((it, i) => {
        const summary = filterSummary(it.filters || {});
        return (
          <button
            key={i}
            onClick={() => open(it)}
            className="flex items-start gap-2.5 px-3 py-2 rounded-lg text-left text-slate-300 hover:bg-white/5 hover:text-white transition-colors"
          >
            <Clock className="w-3.5 h-3.5 mt-0.5 shrink-0 text-slate-500" />
            <span className="min-w-0">
              <span className="block text-xs font-semibold truncate">{it.query || 'Filter only'}</span>
              {summary && <span className="block text-[10px] font-semibold text-slate-500">{summary}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}

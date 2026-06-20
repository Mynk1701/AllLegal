'use client';

// History — placeholder for now. A full, searchable history (replaying stored
// query + filters, the same data the search sidebar shows under "Recent
// Searches") lands in a later pass. Kept as a real route so the nav rail's
// History item has a home.

import { Clock } from 'lucide-react';

export default function HistoryPage() {
  return (
    <main className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-8 py-12">
        <div className="mb-8">
          <h1 className="text-2xl font-black tracking-tight text-slate-900">History</h1>
          <p className="text-sm text-slate-500 font-medium mt-1">
            Every search you run, ready to replay.
          </p>
        </div>

        <div className="text-center py-20">
          <div className="w-16 h-16 bg-slate-50 rounded-3xl flex items-center justify-center mx-auto mb-4">
            <Clock className="w-7 h-7 text-slate-300" />
          </div>
          <p className="text-slate-500 font-medium">Full history view coming soon.</p>
          <p className="text-sm text-slate-400 mt-1">
            For now, your recent searches are in the search sidebar.
          </p>
        </div>
      </div>
    </main>
  );
}

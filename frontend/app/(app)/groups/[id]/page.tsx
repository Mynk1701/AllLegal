'use client';

// Group detail — placeholder for now. The full view (cases in the matter +
// per-case annotations, backed by getGroup / listAnnotations) lands in the
// Groups pass. Kept as a real route so /groups/[id] links don't 404.

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, FolderClosed } from 'lucide-react';

export default function GroupDetailPage() {
  const params = useParams<{ id: string }>();

  return (
    <main className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-8 py-12">
        <Link
          href="/groups"
          className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-slate-900 transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" /> All groups
        </Link>

        <div className="text-center py-20">
          <div className="w-16 h-16 bg-slate-50 rounded-3xl flex items-center justify-center mx-auto mb-4">
            <FolderClosed className="w-7 h-7 text-slate-300" />
          </div>
          <h1 className="font-black text-slate-900">Group detail coming soon</h1>
          <p className="text-sm text-slate-400 mt-1">
            This will show the cases in the group and their annotations.
          </p>
          <p className="text-[11px] font-mono text-slate-300 mt-4">id: {params?.id}</p>
        </div>
      </div>
    </main>
  );
}

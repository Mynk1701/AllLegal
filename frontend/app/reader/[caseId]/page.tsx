'use client';

// Reader route — opened in a NEW TAB from a search result as
//   /reader/<case_id>?chunk=<chunk_id>
// The session cookie is present in the new tab (set by @supabase/ssr) and
// middleware.ts already gates /reader/*, so we just re-fetch client-side with the
// Bearer pattern. This page is a Client Component (uses hooks + ssr:false), so we
// read the route params via useParams/useSearchParams rather than the (Promise)
// page props Next 16 passes to Server Components.

import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Scale } from 'lucide-react';
import { getCaseDetail } from '@/lib/api';
import type { CaseDetail } from '@/lib/reader/types';

// pdfjs touches browser-only APIs (canvas, Worker, DOMMatrix) — never SSR it.
// ssr:false is only legal inside a Client Component, which this is.
const ReaderView = dynamic(() => import('@/components/reader/ReaderView'), {
  ssr: false,
  loading: () => <FullscreenLoader />,
});

function FullscreenLoader() {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-slate-100">
      <div className="flex flex-col items-center gap-4">
        <Scale className="h-9 w-9 animate-bounce text-blue-600" />
        <div className="h-1 w-24 overflow-hidden rounded-full bg-slate-200">
          <div className="h-full origin-left animate-progress bg-blue-600" />
        </div>
      </div>
    </div>
  );
}

export default function ReaderPage() {
  const params = useParams<{ caseId: string }>();
  const searchParams = useSearchParams();
  const caseId = params.caseId;
  const activeChunkId = searchParams.get('chunk');
  const initialGroupId = searchParams.get('group');

  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!caseId) return;
    getCaseDetail(caseId)
      .then((data) => {
        if (!cancelled) setCaseDetail(data);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load case');
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (error) {
    const notLoaded = /\(404\)/.test(error);
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-100 p-10 text-center">
        {notLoaded ? (
          <div className="max-w-xs space-y-2">
            <p className="text-sm font-bold text-slate-700">Not loaded in this demo</p>
            <p className="text-xs font-medium text-slate-400">
              This judgment is in our dataset, but only a subset of cases has been uploaded so far.
            </p>
          </div>
        ) : (
          <p className="text-sm font-semibold text-rose-600">{error}</p>
        )}
      </div>
    );
  }
  if (!caseDetail) return <FullscreenLoader />;

  return <ReaderView caseDetail={caseDetail} activeChunkId={activeChunkId} initialGroupId={initialGroupId} />;
}

// Centralised backend access. Introduces NEXT_PUBLIC_API_URL (falls back to the
// previously-hardcoded localhost:8000) and the Bearer-auth fetch pattern used
// across the app, so the new-tab reader authenticates the same way.

import { createClient } from '@/utils/supabase/client';
import type { CaseDetail } from '@/lib/reader/types';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

/** fetch() against the backend with the current Supabase session as a Bearer
 *  token. The session cookie is present even in a freshly-opened tab, so the
 *  reader can authenticate without any cross-tab handoff. */
export async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`);
  }
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

export async function getCaseDetail(caseId: string): Promise<CaseDetail> {
  const res = await authedFetch(`/api/cases/${encodeURIComponent(caseId)}`);
  if (!res.ok) {
    throw new Error(`Failed to load case ${caseId} (${res.status})`);
  }
  return res.json();
}

// Centralised backend access. Introduces NEXT_PUBLIC_API_URL (falls back to the
// previously-hardcoded localhost:8000) and the Bearer-auth fetch pattern used
// across the app, so the new-tab reader authenticates the same way.

import { createClient } from '@/utils/supabase/client';
import type { CaseDetail } from '@/lib/reader/types';
import type {
  Annotation,
  AnnotationCreateBody,
  Group,
  GroupDetail,
  GroupItem,
} from '@/lib/groups/types';

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

// ==================== Groups & annotations ====================
// Thin typed wrappers over the backend group routes (see app/api/routes/groups.py).

/** authedFetch + JSON, throwing on non-2xx. Pass expectEmpty for 204 routes. */
async function authedJson<T>(path: string, init: RequestInit = {}, expectEmpty = false): Promise<T> {
  const res = await authedFetch(path, init);
  if (!res.ok) {
    throw new Error(`${init.method ?? 'GET'} ${path} failed (${res.status})`);
  }
  return (expectEmpty ? (undefined as T) : await res.json());
}

const jsonInit = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
});

const g = (id: string) => `/api/groups/${encodeURIComponent(id)}`;

export const listGroups = (caseId?: string): Promise<Group[]> =>
  authedJson(`/api/groups${caseId ? `?case_id=${encodeURIComponent(caseId)}` : ''}`);

export const createGroup = (name: string): Promise<Group> =>
  authedJson('/api/groups', jsonInit('POST', { name }));

export const getGroup = (groupId: string): Promise<GroupDetail> => authedJson(g(groupId));

export const renameGroup = (groupId: string, name: string): Promise<Group> =>
  authedJson(g(groupId), jsonInit('PATCH', { name }));

export const deleteGroup = (groupId: string): Promise<void> =>
  authedJson(g(groupId), jsonInit('DELETE'), true);

export const addCaseToGroup = (groupId: string, caseId: string): Promise<GroupItem> =>
  authedJson(`${g(groupId)}/items`, jsonInit('POST', { case_id: caseId }));

export const removeCaseFromGroup = (groupId: string, caseId: string): Promise<void> =>
  authedJson(`${g(groupId)}/items/${encodeURIComponent(caseId)}`, jsonInit('DELETE'), true);

export const listAnnotations = (groupId: string, caseId: string): Promise<Annotation[]> =>
  authedJson(`${g(groupId)}/annotations?case_id=${encodeURIComponent(caseId)}`);

export const createAnnotation = (groupId: string, body: AnnotationCreateBody): Promise<Annotation> =>
  authedJson(`${g(groupId)}/annotations`, jsonInit('POST', body));

export const updateAnnotation = (
  groupId: string,
  annotationId: string,
  patch: { color?: string; comment?: string },
): Promise<Annotation> =>
  authedJson(`${g(groupId)}/annotations/${encodeURIComponent(annotationId)}`, jsonInit('PATCH', patch));

export const deleteAnnotation = (groupId: string, annotationId: string): Promise<void> =>
  authedJson(
    `${g(groupId)}/annotations/${encodeURIComponent(annotationId)}`,
    jsonInit('DELETE'),
    true,
  );

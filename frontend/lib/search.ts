// Shared search vocabulary. The canonical SearchFilters shape lives here (not in
// a component) so the FilterBar, the search page, and the sidebar History tree
// all agree on it. Also the URL <-> filters codec: a History click deep-links
// into /search?<encoded>, and the search page replays it — which also makes any
// search a shareable/bookmarkable URL.

export interface SearchFilters {
  court?: string[];
  case_type?: string[];
  verdict?: string[];
  acts_cited?: string[];
  sections_cited?: string[];
  bench_strength?: (number | string)[];
  year_from?: string | number;
  year_to?: string | number;
}

export interface HistoryItem {
  query: string | null;
  filters: SearchFilters;
  timestamp: string;
}

// Param names match the backend /api/search query params (see runSearch), so the
// same encoding round-trips through both the URL and the API call.
export function filtersToQueryString(query: string, f: SearchFilters): string {
  const p = new URLSearchParams();
  if (query) p.set('query', query);
  (f.court ?? []).forEach((v) => p.append('court', String(v)));
  (f.case_type ?? []).forEach((v) => p.append('case_type', String(v)));
  (f.verdict ?? []).forEach((v) => p.append('verdict', String(v)));
  (f.acts_cited ?? []).forEach((v) => p.append('acts_cited', String(v)));
  (f.sections_cited ?? []).forEach((v) => p.append('sections_cited', String(v)));
  (f.bench_strength ?? []).forEach((v) => p.append('bench_strength', String(v)));
  if (f.year_from) p.set('year_from', String(f.year_from));
  if (f.year_to) p.set('year_to', String(f.year_to));
  return p.toString();
}

export function parseSearchParams(sp: URLSearchParams): { query: string; filters: SearchFilters } {
  return {
    query: sp.get('query') ?? '',
    filters: {
      court: sp.getAll('court'),
      case_type: sp.getAll('case_type'),
      verdict: sp.getAll('verdict'),
      acts_cited: sp.getAll('acts_cited'),
      sections_cited: sp.getAll('sections_cited'),
      bench_strength: sp.getAll('bench_strength'),
      year_from: sp.get('year_from') ?? undefined,
      year_to: sp.get('year_to') ?? undefined,
    },
  };
}

// Compact "N filters" summary for a recent-search row.
export function filterSummary(f: SearchFilters): string {
  const c =
    (f.court?.length ?? 0) +
    (f.case_type?.length ?? 0) +
    (f.verdict?.length ?? 0) +
    (f.acts_cited?.length ?? 0) +
    (f.sections_cited?.length ?? 0) +
    (f.bench_strength?.length ?? 0) +
    (f.year_from || f.year_to ? 1 : 0);
  return c > 0 ? `${c} filter${c > 1 ? 's' : ''}` : '';
}

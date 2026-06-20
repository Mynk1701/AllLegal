'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Search, BookOpen, Scale, Clock, ChevronRight, FileText, Info, Sparkles, Gavel, FolderPlus, X } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { createClient } from '@/utils/supabase/client';
import { SearchResponse, CaseResult, MatchedChunk, Facets } from '@/types/legal';
import { ROLE_COLORS, ROLE_DISPLAY_NAMES } from '@/lib/reader/roles';
import GroupPicker from '@/components/groups/GroupPicker';
import FilterBar from '@/components/search/FilterBar';
import { parseSearchParams, filterSummary, type HistoryItem, type SearchFilters } from '@/lib/search';

// Utility for tailwind classes
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// In-app reader URL, jumping to the top matched chunk when there is one.
const readerHref = (c: CaseResult) => {
  const chunk = c.matched_chunks[0]?.chunk_id;
  return `/reader/${encodeURIComponent(c.case_id)}${chunk ? `?chunk=${encodeURIComponent(chunk)}` : ''}`;
};

const formatTagName = (tag: string) => {
  return tag.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

function SearchWorkspace() {
  const [query, setQuery] = useState('');
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [selectedCase, setSelectedCase] = useState<CaseResult | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [searchHistory, setSearchHistory] = useState<HistoryItem[]>([]);
  // Filter option values (court/case_type/verdict/...) come from the backend's
  // own index, via GET /api/facets — never hardcoded here. Empty arrays for a
  // field (e.g. case_type, until it's actually extracted by the pipeline) mean
  // that filter section simply doesn't render, instead of offering options
  // that are guaranteed to return zero results.
  const [facets, setFacets] = useState<Facets | null>(null);

  // Real Filter States
  const [selectedCourts, setSelectedCourts] = useState<string[]>([]);
  const [selectedCaseTypes, setSelectedCaseTypes] = useState<string[]>([]);
  const [selectedVerdicts, setSelectedVerdicts] = useState<string[]>([]);
  const [selectedActs, setSelectedActs] = useState<string[]>([]);
  const [selectedSections, setSelectedSections] = useState<string[]>([]);
  const [selectedBench, setSelectedBench] = useState<string[]>([]);
  const [yearFrom, setYearFrom] = useState<string>('');
  const [yearTo, setYearTo] = useState<string>('');

  const router = useRouter();
  const supabase = createClient();
  const searchParams = useSearchParams();
  const spString = searchParams.toString();

  async function fetchHistory() {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch('http://localhost:8000/api/search/history', {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setSearchHistory(data);
      }
    } catch (err) {
      console.error('History fetch error:', err);
    }
  }

  // Unfiltered, query-less facets — populates the filter checkboxes with
  // whatever values/counts actually exist in the index right now. Called once
  // on load; refreshed with query-aware, drill-down counts after every search.
  async function fetchFacets() {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch('http://localhost:8000/api/facets', {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });
      if (response.ok) {
        const data: Facets = await response.json();
        setFacets(data);
      }
    } catch (err) {
      console.error('Facets fetch error:', err);
    }
  }

  // Authentication Check
  useEffect(() => {
    async function getUser() {
      try {
        const { data, error } = await supabase.auth.getUser();
        if (error || !data?.user) {
          router.push('/login');
        } else {
          setUser(data.user);
          fetchHistory();
          fetchFacets();
        }
      } catch (err) {
        console.error("Unexpected Auth Error:", err);
      }
    }
    getUser();
  }, [router, supabase.auth]);

  // Build the backend filter set from the current filter UI state.
  const collectFilters = (): SearchFilters => ({
    court: selectedCourts,
    case_type: selectedCaseTypes,
    verdict: selectedVerdicts,
    acts_cited: selectedActs,
    sections_cited: selectedSections,
    bench_strength: selectedBench,
    year_from: yearFrom || undefined,
    year_to: yearTo || undefined,
  });

  // Single source of truth for running a search. Takes query + filters EXPLICITLY
  // (never reads component state), so the form and a history replay produce
  // identical, deterministic results — search is a pure function of {query, filters}.
  const runSearch = async (queryStr: string, filters: SearchFilters) => {
    setIsSearching(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      // Standard API names from search.py.
      const params = new URLSearchParams();
      if (queryStr) params.append('query', queryStr);
      (filters.court ?? []).forEach(c => params.append('court', c));
      (filters.case_type ?? []).forEach(t => params.append('case_type', t));
      (filters.verdict ?? []).forEach(v => params.append('verdict', v));
      (filters.acts_cited ?? []).forEach(a => params.append('acts_cited', String(a)));
      (filters.sections_cited ?? []).forEach(s => params.append('sections_cited', String(s)));
      (filters.bench_strength ?? []).forEach(b => params.append('bench_strength', String(b)));
      if (filters.year_from) params.append('year_from', String(filters.year_from));
      if (filters.year_to) params.append('year_to', String(filters.year_to));

      const response = await fetch(`http://localhost:8000/api/search?${params.toString()}`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` }
      });

      if (response.ok) {
        const data: SearchResponse = await response.json();
        setSearchResponse(data);
        setSelectedCase(data.results.length > 0 ? data.results[0] : null);
        setFacets(data.facets); // Drill-down counts for the active query + filters
        fetchHistory(); // Refresh history
      }
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setIsSearching(false);
    }
  };

  // Form submit → search the current query + active filters. No-op when there's
  // nothing to search (empty query AND no active filters).
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const filters = collectFilters();
    if (!query.trim() && !filterSummary(filters)) return;
    runSearch(query, filters);
  };

  // History click → replay the STORED query + filters directly. The stored
  // filters are already the exact canonical index values (court "SC", verdict
  // "partly_allowed", …) — same as what the facet-driven controls use as their
  // value now, so no reverse-mapping is needed; we feed them back into state
  // directly, instead of reading state setQuery/setX have only just *scheduled*.
  const applyHistory = (item: HistoryItem) => {
    const f = item.filters || {};
    setQuery(item.query || '');
    setSelectedCourts(f.court ?? []);
    setSelectedCaseTypes(f.case_type ?? []);
    setSelectedVerdicts(f.verdict ?? []);
    setSelectedActs(f.acts_cited ?? []);
    setSelectedSections(f.sections_cited ?? []);
    setSelectedBench((f.bench_strength ?? []).map(String));
    setYearFrom(f.year_from != null ? String(f.year_from) : '');
    setYearTo(f.year_to != null ? String(f.year_to) : '');
    runSearch(item.query || '', f);
  };

  // Stage a full next-filter set from the FilterBar. This ONLY updates the
  // filter state (so the pills/chips/sliders reflect the change) — it does NOT
  // run a search. Nothing is applied until the user submits the query bar
  // (handleSearch), which reads the current staged filters via collectFilters().
  const stageFilters = (next: SearchFilters) => {
    setSelectedCourts(next.court ?? []);
    setSelectedCaseTypes(next.case_type ?? []);
    setSelectedVerdicts(next.verdict ?? []);
    setSelectedActs(next.acts_cited ?? []);
    setSelectedSections(next.sections_cited ?? []);
    setSelectedBench((next.bench_strength ?? []).map(String));
    setYearFrom(next.year_from != null ? String(next.year_from) : '');
    setYearTo(next.year_to != null ? String(next.year_to) : '');
  };

  // Replay a search encoded in the URL — e.g. a sidebar History click navigates
  // to /search?query=…&court=…, and this picks it up and runs it. Manual
  // filtering/searching doesn't touch the URL, so this only fires on deep-links.
  useEffect(() => {
    if (!user || !spString) return;
    const { query: q, filters } = parseSearchParams(new URLSearchParams(spString));
    setQuery(q);
    stageFilters(filters);
    runSearch(q, filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, spString]);

  if (!user) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Scale className="w-10 h-10 text-blue-600 animate-bounce" />
          <div className="h-1 w-24 bg-slate-200 rounded-full overflow-hidden">
            <div className="h-full bg-blue-600 animate-progress origin-left" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 min-w-0 overflow-hidden relative z-10">
      {/* MIDDLE - SEARCH & RESULTS */}
      <main className="flex-1 flex flex-col min-w-0 relative z-10">
        <header className="px-8 pt-6 pb-4 bg-white/40 backdrop-blur-md border-b border-slate-200/60 sticky top-0 z-30">
          <div className="max-w-5xl mx-auto space-y-3">
            <form onSubmit={handleSearch} className="relative group">
              <div className="absolute inset-0 bg-blue-500/5 rounded-2xl blur-xl transition-all group-focus-within:bg-blue-500/10" />
              <div className="relative flex items-center">
                <Search className="absolute left-5 w-5 h-5 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask a legal question or cite a statute..."
                  className="w-full pl-14 pr-32 py-4 bg-white border border-slate-200 rounded-2xl text-[15px] font-medium shadow-xl shadow-slate-200/30 focus:outline-none focus:ring-4 focus:ring-blue-500/5 focus:border-blue-500 transition-all placeholder-slate-400"
                />
                <div className="absolute right-3 flex items-center gap-2">
                  <span className="hidden sm:flex px-2 py-1 bg-slate-100 text-[10px] font-bold text-slate-400 rounded-md border border-slate-200 tracking-tighter uppercase">⌘ K</span>
                  <button
                    type="submit"
                    disabled={!query.trim() && !filterSummary(collectFilters())}
                    className="bg-blue-600 hover:bg-blue-700 text-white p-2 rounded-xl transition-all shadow-lg shadow-blue-500/20 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none disabled:active:scale-100"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </form>

            <FilterBar
              facets={facets}
              filters={collectFilters()}
              onChange={stageFilters}
              onClearAll={() => stageFilters({})}
            />
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-8 pb-12">
          <div className="max-w-5xl mx-auto mt-8">
            {!searchResponse && !isSearching ? (
              /* EMPTY STATE — pre-first-search. Recent searches kept reachable
                 here now that the left history sidebar is gone. (Groups cards
                 land in the next pass.) */
              <div className="mt-12">
                <h2 className="text-3xl font-black tracking-tight text-slate-900">What are you researching?</h2>
                <p className="text-base text-slate-500 font-medium mt-2 mb-10">
                  Ask a legal question, cite a statute, or narrow by court and outcome above.
                </p>
                {searchHistory.length > 0 ? (
                  <>
                    <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
                      <Clock className="w-3.5 h-3.5" /> Recent Searches
                    </h3>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {searchHistory.slice(0, 9).map((item, index) => {
                        const summary = filterSummary(item.filters);
                        return (
                          <button
                            key={index}
                            onClick={() => applyHistory(item)}
                            className="group flex items-center gap-3 px-4 py-4 rounded-2xl bg-white/70 border border-slate-200/80 hover:bg-white hover:border-blue-300 hover:shadow-lg hover:shadow-blue-500/5 transition-all text-left"
                          >
                            <span className="w-9 h-9 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0 group-hover:bg-blue-50 group-hover:border-blue-100 transition-colors">
                              <Clock className="w-4 h-4 text-slate-400 group-hover:text-blue-500" />
                            </span>
                            <span className="min-w-0">
                              <span className="block text-sm font-bold text-slate-700 truncate">{item.query || 'Filter only'}</span>
                              {summary && <span className="block text-[11px] font-semibold text-slate-400">{summary}</span>}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <div className="rounded-3xl border border-dashed border-slate-200 bg-white/40 px-8 py-16 text-center">
                    <Search className="w-10 h-10 text-slate-200 mx-auto mb-3" />
                    <p className="text-slate-500 font-semibold">Your searches will show up here.</p>
                    <p className="text-sm text-slate-400 mt-1">Start by typing a question above.</p>
                  </div>
                )}
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between mb-8">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-blue-500" />
                    <h2 className="text-sm font-bold text-slate-600">Top Semantic Matches</h2>
                  </div>
                  {searchResponse && (
                    <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">
                      Search Latency: {searchResponse.took_ms.toFixed(1)}ms
                    </p>
                  )}
                </div>

                {isSearching ? (
                  <div className="space-y-6">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="h-44 bg-white/60 border border-slate-200 rounded-3xl animate-pulse" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-6">
                    {searchResponse?.results.map((result) => (
                      <div
                        key={result.case_id}
                        onClick={() => setSelectedCase(result)}
                        className={cn(
                          "group p-6 rounded-[32px] border transition-all cursor-pointer relative overflow-hidden",
                          selectedCase?.case_id === result.case_id
                            ? "bg-white border-blue-500 shadow-2xl shadow-blue-500/10 ring-1 ring-blue-500"
                            : "bg-white/70 border-slate-200/80 hover:bg-white hover:border-slate-300 hover:shadow-xl hover:shadow-slate-200/40"
                        )}
                      >
                        {/* Relevance bar */}
                        <div className="absolute top-0 left-0 bottom-0 w-1 bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />

                        <div className="flex justify-between items-start gap-4 mb-4">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <h4 className="font-extrabold text-lg text-slate-900 leading-tight group-hover:text-blue-600 transition-colors">
                                {result.case_name}
                              </h4>
                              {result.score ? (
                                <div className="px-2 py-0.5 bg-blue-50 text-blue-600 text-[10px] font-bold rounded-full border border-blue-100 shrink-0">
                                  {Math.round(result.score * 100)}% Match
                                </div>
                              ) : (
                                <div className="px-2 py-0.5 bg-slate-50 text-slate-400 text-[10px] font-bold rounded-full border border-slate-100 shrink-0">
                                  Date Ranked
                                </div>
                              )}
                            </div>
                            <div className="flex items-center gap-3">
                               <span className="text-[11px] font-bold text-blue-600 uppercase tracking-widest">{result.court}</span>
                               <span className="w-1 h-1 bg-slate-300 rounded-full" />
                               <span className="text-[11px] font-bold text-slate-400">{result.year}</span>
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-2">
                            {result.matched_chunks[0]?.chunk_type && (
                              <div className={cn(
                                "px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-[0.1em] border ring-1",
                                ROLE_COLORS[result.matched_chunks[0].chunk_type] || 'bg-slate-50 text-slate-600'
                              )}>
                                {ROLE_DISPLAY_NAMES[result.matched_chunks[0].chunk_type] || result.matched_chunks[0].chunk_type}
                              </div>
                            )}
                            {result.verdict.length > 0 && (
                              <div className="flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[9px] font-bold uppercase rounded border border-emerald-100">
                                <Gavel className="w-2.5 h-2.5" />
                                {formatTagName(result.verdict[0])}
                              </div>
                            )}
                          </div>
                        </div>

                        <p className="text-sm text-slate-600 font-medium leading-[1.7] mb-6 line-clamp-3">
                          {result.matched_chunks[0]?.chunk_text || 'No preview available.'}
                        </p>

                        <div className="flex flex-wrap gap-2">
                          {/* Show specific sections first, then acts if no sections */}
                          {(result.sections_cited.length > 0 ? result.sections_cited : result.acts_cited).slice(0, 4).map(tag => (
                            <div key={tag} className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 text-slate-600 text-[10px] font-bold rounded-xl border border-slate-200/60 group-hover:bg-blue-50/50 group-hover:border-blue-100 transition-all">
                              <FileText className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-500" />
                              {tag}
                            </div>
                          ))}
                          {(result.sections_cited.length > 4 || (result.sections_cited.length === 0 && result.acts_cited.length > 4)) && (
                            <span className="text-[10px] font-bold text-slate-400 px-2 py-1.5">
                              +{Math.max(result.sections_cited.length, result.acts_cited.length) - 4} more
                            </span>
                          )}
                        </div>
                      </div>
                    ))}

                    {searchResponse?.results.length === 0 && !isSearching && (
                      <div className="text-center py-20">
                        <Info className="w-12 h-12 text-slate-200 mx-auto mb-4" />
                        <p className="text-slate-500 font-medium">No cases found matching your criteria.</p>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>

      {/* RIGHT PANE — slides in only when a result is selected */}
      {selectedCase && (
        <aside className="w-[480px] border-l border-slate-200 bg-white flex flex-col shrink-0 relative z-30 shadow-[-10px_0_30px_rgba(0,0,0,0.02)] animate-in slide-in-from-right-8 duration-200">
            <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-white/80 backdrop-blur-md sticky top-0 z-10">
              <h3 className="font-extrabold text-slate-900 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-blue-600" /> Analysis
              </h3>
              <button
                onClick={() => setSelectedCase(null)}
                aria-label="Close analysis"
                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex gap-2 px-8 pt-5">
              <a
                href={readerHref(selectedCase)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 py-2.5 bg-slate-900 text-white rounded-xl font-bold text-xs hover:bg-slate-800 transition-all flex items-center justify-center gap-2 active:scale-[0.98]"
              >
                <FileText className="w-3.5 h-3.5" />
                Open in Reader
              </a>
              <button
                onClick={() => setPickerOpen(true)}
                className="flex-1 py-2.5 bg-white border border-slate-200 text-slate-700 rounded-xl font-bold text-xs hover:bg-slate-50 transition-all flex items-center justify-center gap-2 active:scale-[0.98]"
              >
                <FolderPlus className="w-3.5 h-3.5" />
                Add to group
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-8 py-10 space-y-10">
              <div className="space-y-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="text-[10px] font-black text-blue-600 uppercase tracking-[0.2em]">Judgment Extract</p>
                    {selectedCase.verdict.length > 0 && (
                      <span className="px-2 py-0.5 bg-emerald-600 text-white text-[9px] font-black uppercase rounded shadow-sm">
                        {formatTagName(selectedCase.verdict[0])}
                      </span>
                    )}
                  </div>
                  <h2 className="text-2xl font-black leading-tight text-slate-900 tracking-tight italic">
                    “{selectedCase.case_name}”
                  </h2>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="text-[11px] bg-slate-900 text-white px-3 py-1 rounded-lg font-bold">
                    {selectedCase.citation || `EST. ${selectedCase.year}`}
                  </span>
                  <span className="text-[11px] bg-blue-50 text-blue-700 px-3 py-1 rounded-lg font-bold border border-blue-100">
                    {selectedCase.court}
                  </span>
                  <span className="text-[11px] bg-slate-50 text-slate-500 px-3 py-1 rounded-lg font-bold border border-slate-100">
                    Bench: {selectedCase.bench_strength || selectedCase.bench.length || 'Unknown'}
                  </span>
                </div>
              </div>

              {selectedCase.matched_chunks.map((chunk, idx) => (
                <div key={chunk.chunk_id} className="relative">
                  <div className="absolute -left-6 top-0 bottom-0 w-1 bg-blue-600/20 rounded-full" />
                  <div className="flex items-center gap-2 mb-4">
                    <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                    <span className="text-[11px] font-black uppercase tracking-[0.2em] text-blue-600">
                      {ROLE_DISPLAY_NAMES[chunk.chunk_type || ''] || chunk.chunk_type || `Match ${idx + 1}`}
                    </span>
                  </div>
                  <p className="text-slate-800 leading-[1.8] text-[17px] font-serif font-medium selection:bg-blue-200">
                    {chunk.chunk_text}
                  </p>
                </div>
              ))}

              {(selectedCase.sections_cited.length > 0 || selectedCase.acts_cited.length > 0) && (
                <div className="space-y-4">
                  <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2">
                    <Info className="w-3.5 h-3.5" /> Contextual Landmarks
                  </h4>
                  <div className="grid gap-2">
                    {(selectedCase.sections_cited.length > 0 ? selectedCase.sections_cited : selectedCase.acts_cited).map(tag => (
                      <div key={tag} className="group flex items-center justify-between p-4 bg-slate-50/50 hover:bg-white rounded-2xl border border-slate-100 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-500/5 transition-all cursor-pointer">
                        <div className="flex items-center gap-3">
                           <div className="w-8 h-8 rounded-lg bg-white border border-slate-100 flex items-center justify-center text-blue-600 group-hover:scale-110 transition-transform">
                              <FileText className="w-4 h-4" />
                           </div>
                           <span className="text-xs font-bold text-slate-700">{tag}</span>
                        </div>
                        <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-blue-500 group-hover:translate-x-1 transition-all" />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {pickerOpen && (
                <GroupPicker
                  caseId={selectedCase.case_id}
                  caseName={selectedCase.case_name}
                  onClose={() => setPickerOpen(false)}
                />
              )}
            </div>
        </aside>
      )}
    </div>
  );
}

// useSearchParams() requires a Suspense boundary, so the workspace renders inside one.
export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchWorkspace />
    </Suspense>
  );
}

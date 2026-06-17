'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Filter, BookOpen, Scale, Clock, ChevronRight, FileText, ExternalLink, Info, LogOut, User, Sparkles, TrendingUp, History, Gavel, AlertCircle } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { createClient } from '@/utils/supabase/client';
import { logout } from './auth/actions';
import { SearchResponse, CaseResult, MatchedChunk } from '@/types/legal';
import { ROLE_COLORS, ROLE_DISPLAY_NAMES } from '@/lib/reader/roles';

// Utility for tailwind classes
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// In-app reader URL, jumping to the top matched chunk when there is one.
const readerHref = (c: CaseResult) => {
  const chunk = c.matched_chunks[0]?.chunk_id;
  return `/reader/${encodeURIComponent(c.case_id)}${chunk ? `?chunk=${encodeURIComponent(chunk)}` : ''}`;
};

// Helper to parse verdict JSON string if needed
const parseVerdict = (verdict: any): string[] => {
  if (!verdict) return [];
  if (Array.isArray(verdict)) return verdict;
  try {
    const parsed = JSON.parse(verdict);
    return Array.isArray(parsed) ? parsed : [String(parsed)];
  } catch (e) {
    return [String(verdict)];
  }
};

const formatTagName = (tag: string) => {
  return tag.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

// Backend filter set (already-normalized values as stored/replayed).
interface SearchFilters {
  court?: string[];
  case_type?: string[];
  verdict?: string[];
  acts_cited?: string[];
  sections_cited?: string[];
  bench_strength?: (number | string)[];
  year_from?: string | number;
  year_to?: string | number;
}

// Define History Item Type from API
interface HistoryItem {
  query: string | null;
  filters: SearchFilters;
  timestamp: string;
}

export default function LegalSearchApp() {
  const [query, setQuery] = useState('');
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [selectedCase, setSelectedCase] = useState<CaseResult | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [searchHistory, setSearchHistory] = useState<HistoryItem[]>([]);
  
  // Real Filter States
  const [selectedCourts, setSelectedCourts] = useState<string[]>([]);
  const [selectedCaseTypes, setSelectedCaseTypes] = useState<string[]>([]);
  const [selectedVerdicts, setSelectedVerdicts] = useState<string[]>([]);
  const [actsCited, setActsCited] = useState<string>('');
  const [sectionsCited, setSectionsCited] = useState<string>('');
  const [yearFrom, setYearFrom] = useState<string>('');
  const [yearTo, setYearTo] = useState<string>('');

  const router = useRouter();
  const supabase = createClient();

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

  // Authentication Check
  useEffect(() => {
    async function getUser() {
      console.log("🔍 Checking auth status...");
      try {
        const { data, error } = await supabase.auth.getUser();
        console.log("📡 Supabase Response:", { user: data?.user, error });
        
        if (error || !data?.user) {
          console.log("❌ No user found, redirecting to /login");
          router.push('/login');
        } else {
          console.log("✅ User authenticated:", data.user.email);
          setUser(data.user);
          fetchHistory(); 
        }
      } catch (err) {
        console.error("💥 Unexpected Auth Error:", err);
      }
    }
    getUser();
  }, [router, supabase.auth]);

  // Build the backend filter set from the current sidebar UI state.
  const collectFilters = (): SearchFilters => ({
    court: selectedCourts,
    case_type: selectedCaseTypes,
    verdict: selectedVerdicts,
    acts_cited: actsCited ? actsCited.split(',').map(s => s.trim()).filter(Boolean) : [],
    sections_cited: sectionsCited ? sectionsCited.split(',').map(s => s.trim()).filter(Boolean) : [],
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
        fetchHistory(); // Refresh history
      }
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setIsSearching(false);
    }
  };

  // Form submit → search the current query + sidebar filters.
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch(query, collectFilters());
  };

  // History click → replay the STORED query + filters directly. The stored
  // filters are already normalized (court "SC", verdict "partly_allowed", …) and
  // normalization is idempotent, so replaying them reproduces the original
  // results exactly — instead of reading the sidebar state, which setQuery/setX
  // have only just *scheduled* and not yet applied. We also reflect the values
  // back into the sidebar (best-effort reverse of the backend normalization) so
  // the UI matches what was searched.
  const applyHistory = (item: HistoryItem) => {
    const f = item.filters || {};
    setQuery(item.query || '');
    setSelectedCourts((f.court ?? []).map(c => (c === 'SC' ? 'Supreme Court' : c)));
    setSelectedCaseTypes((f.case_type ?? []).map(t => t.charAt(0).toUpperCase() + t.slice(1)));
    setSelectedVerdicts(
      (f.verdict ?? []).map(v => v.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')),
    );
    setActsCited((f.acts_cited ?? []).join(', '));
    setSectionsCited((f.sections_cited ?? []).join(', '));
    setYearFrom(f.year_from != null ? String(f.year_from) : '');
    setYearTo(f.year_to != null ? String(f.year_to) : '');
    runSearch(item.query || '', f);
  };

  const toggleFilter = (list: string[], setList: (v: string[]) => void, value: string) => {
    if (list.includes(value)) {
      setList(list.filter(i => i !== value));
    } else {
      setList([...list, value]);
    }
  };

  const handleLogout = async () => {
    await logout();
  };

  if (!user) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-slate-50">
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
    <div className="flex h-screen bg-slate-50 text-slate-900 font-sans overflow-hidden mesh-gradient">
      {/* LEFT SIDEBAR - PREMIUM GLASS */}
      <aside className="w-72 border-r border-slate-200 bg-white/80 backdrop-blur-xl flex flex-col shrink-0 z-20">
        <div className="p-6 border-b border-slate-100 flex items-center gap-3">
          <div className="p-2 bg-blue-600 rounded-xl shadow-lg shadow-blue-500/20">
            <Scale className="w-6 h-6 text-white" />
          </div>
          <span className="font-extrabold text-xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-600">AllLegal</span>
        </div>
        
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          <div>
            <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] mb-4">Recent Searches</h3>
            <nav className="space-y-1">
              {searchHistory.map((item, index) => (
                <button
                  key={index}
                  onClick={() => applyHistory(item)}
                  className="w-full flex items-center gap-3 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-lg transition-all truncate"
                >
                  <Clock className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">{item.query || 'Filter Only'}</span>
                </button>
              ))}
            </nav>
          </div>

          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">Refinement</h3>
              <button 
                onClick={() => {
                  setSelectedCourts([]);
                  setSelectedCaseTypes([]);
                  setSelectedVerdicts([]);
                  setYearFrom('');
                  setYearTo('');
                }}
                className="text-[10px] font-bold text-blue-600 uppercase hover:text-blue-700 transition-colors"
              >
                Clear
              </button>
            </div>
            
            <div className="space-y-6">
              {/* JURISDICTION / COURT */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-slate-700 ml-1">Jurisdiction</label>
                <div className="grid grid-cols-1 gap-1.5">
                  {['Supreme Court', 'Delhi High Court', 'Bombay High Court'].map(court => (
                    <label key={court} className="flex items-center gap-3 px-3 py-2 rounded-xl border border-slate-100 hover:bg-slate-50 cursor-pointer transition-all">
                      <input 
                        type="checkbox" 
                        checked={selectedCourts.includes(court)}
                        onChange={() => toggleFilter(selectedCourts, setSelectedCourts, court)}
                        className="w-4 h-4 rounded-md border-slate-300 text-blue-600 focus:ring-blue-500/20" 
                      />
                      <span className="text-xs font-semibold text-slate-600">{court}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* CASE TYPE */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-slate-700 ml-1">Case Type</label>
                <div className="grid grid-cols-1 gap-1.5">
                  {['Criminal', 'Civil', 'Constitutional', 'Tax'].map(type => (
                    <label key={type} className="flex items-center gap-3 px-3 py-2 rounded-xl border border-slate-100 hover:bg-slate-50 cursor-pointer transition-all">
                      <input 
                        type="checkbox" 
                        checked={selectedCaseTypes.includes(type)}
                        onChange={() => toggleFilter(selectedCaseTypes, setSelectedCaseTypes, type)}
                        className="w-4 h-4 rounded-md border-slate-300 text-blue-600 focus:ring-blue-500/20" 
                      />
                      <span className="text-xs font-semibold text-slate-600">{type}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* VERDICT */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-slate-700 ml-1">Outcome</label>
                <div className="grid grid-cols-1 gap-1.5">
                  {['Allowed', 'Dismissed', 'Partly Allowed'].map(verdict => (
                    <label key={verdict} className="flex items-center gap-3 px-3 py-2 rounded-xl border border-slate-100 hover:bg-slate-50 cursor-pointer transition-all">
                      <input 
                        type="checkbox" 
                        checked={selectedVerdicts.includes(verdict)}
                        onChange={() => toggleFilter(selectedVerdicts, setSelectedVerdicts, verdict)}
                        className="w-4 h-4 rounded-md border-slate-300 text-blue-600 focus:ring-blue-500/20" 
                      />
                      <span className="text-xs font-semibold text-slate-600">{verdict}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* YEAR RANGE */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-slate-700 ml-1">Year Range</label>
                <div className="flex gap-2 px-1">
                  <input 
                    type="text" 
                    placeholder="From" 
                    value={yearFrom}
                    onChange={(e) => setYearFrom(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-[10px] font-bold focus:ring-2 focus:ring-blue-500/20 outline-none" 
                  />
                  <input 
                    type="text" 
                    placeholder="To" 
                    value={yearTo}
                    onChange={(e) => setYearTo(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-[10px] font-bold focus:ring-2 focus:ring-blue-500/20 outline-none" 
                  />
                </div>
              </div>

              {/* ACTS & SECTIONS */}
              <div className="space-y-4 pt-2 border-t border-slate-100">
                <div className="space-y-2">
                  <label className="text-[11px] font-bold text-slate-700 ml-1 flex items-center gap-2">
                    <FileText className="w-3 h-3" /> Acts Cited
                  </label>
                  <input 
                    type="text" 
                    placeholder="e.g. IPC, BNSS" 
                    value={actsCited}
                    onChange={(e) => setActsCited(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs font-semibold focus:ring-2 focus:ring-blue-500/20 outline-none" 
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-bold text-slate-700 ml-1 flex items-center gap-2">
                    <History className="w-3 h-3" /> Sections
                  </label>
                  <input 
                    type="text" 
                    placeholder="e.g. 302, 167" 
                    value={sectionsCited}
                    onChange={(e) => setSectionsCited(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs font-semibold focus:ring-2 focus:ring-blue-500/20 outline-none" 
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* User Profile */}
        <div className="p-6 border-t border-slate-100 bg-white/50 backdrop-blur-md">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
              <User className="w-5 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-bold text-slate-900 truncate">{user.email}</p>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-tighter">Verified Counsel</p>
              </div>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 py-3 text-xs font-bold text-rose-600 hover:bg-rose-50 rounded-xl transition-all border border-transparent hover:border-rose-100"
          >
            <LogOut className="w-3.5 h-3.5" /> Sign Out
          </button>
        </div>
      </aside>

      {/* MIDDLE - SEARCH & RESULTS */}
      <main className="flex-1 flex flex-col min-w-0 relative z-10">
        <header className="px-8 py-6 bg-white/40 backdrop-blur-md border-b border-slate-200/60 sticky top-0 z-30">
          <form onSubmit={handleSearch} className="relative max-w-4xl mx-auto group">
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
                <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white p-2 rounded-xl transition-all shadow-lg shadow-blue-500/20 active:scale-95">
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </form>
        </header>

        <div className="flex-1 overflow-y-auto px-8 pb-12">
          <div className="max-w-4xl mx-auto mt-8">
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
                        {parseVerdict(result.verdict).length > 0 && (
                          <div className="flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[9px] font-bold uppercase rounded border border-emerald-100">
                            <Gavel className="w-2.5 h-2.5" />
                            {formatTagName(parseVerdict(result.verdict)[0])}
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
          </div>
        </div>
      </main>

      {/* RIGHT PANE - JUDGMENT READER */}
      <aside className="w-[480px] border-l border-slate-200 bg-white flex flex-col shrink-0 relative z-30 shadow-[-10px_0_30px_rgba(0,0,0,0.02)]">
        {selectedCase ? (
          <>
            <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-white/80 backdrop-blur-md sticky top-0 z-10">
              <h3 className="font-extrabold text-slate-900 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-blue-600" /> Analysis
              </h3>
              <div className="flex gap-2">
                <a 
                  href={selectedCase.pdf_url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="p-2 hover:bg-slate-50 rounded-lg transition-colors border border-slate-100"
                >
                  <ExternalLink className="w-4 h-4 text-slate-400" />
                </a>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto px-8 py-10 space-y-10">
              <div className="space-y-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="text-[10px] font-black text-blue-600 uppercase tracking-[0.2em]">Judgment Extract</p>
                    {parseVerdict(selectedCase.verdict).length > 0 && (
                      <span className="px-2 py-0.5 bg-emerald-600 text-white text-[9px] font-black uppercase rounded shadow-sm">
                        {formatTagName(parseVerdict(selectedCase.verdict)[0])}
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

              <a
                href={readerHref(selectedCase)}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-4 bg-slate-900 text-white rounded-2xl font-bold text-sm shadow-2xl shadow-slate-900/20 hover:bg-slate-800 transition-all flex items-center justify-center gap-3 group active:scale-[0.98]"
              >
                <FileText className="w-4 h-4 group-hover:rotate-12 transition-transform" />
                Open in Reader
              </a>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
            <div className="w-20 h-20 bg-slate-50 rounded-[2rem] flex items-center justify-center mb-6 rotate-12">
              <Scale className="w-10 h-10 text-slate-200 -rotate-12" />
            </div>
            <h3 className="font-black text-slate-900 mb-2">Detailed Insight</h3>
            <p className="text-sm text-slate-400 font-medium">Select a result to extract reasoning, citations, and full textual context.</p>
          </div>
        )}
      </aside>
    </div>
  );
}

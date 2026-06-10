'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Filter, BookOpen, Scale, Clock, ChevronRight, FileText, ExternalLink, Info, LogOut, User, Sparkles, TrendingUp, History } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { createClient } from '@/utils/supabase/client';
import { logout } from './auth/actions';

// Utility for tailwind classes
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Mock Data
const MOCK_RESULTS = [
  {
    chunk_id: '1',
    case_name: 'Kesavananda Bharati v. State of Kerala',
    court: 'Supreme Court of India',
    year: 1973,
    segment_label: 'RatioOfTheDecision',
    raw_text: 'The power of amendment under Article 368 does not include the power to alter the basic structure or framework of the Constitution. There are inherent limitations on the amending power of the Parliament which prevents it from damaging the essential features of the Constitution.',
    page_number: 45,
    statute_tags: ['Constitution Article 368', 'Article 13'],
    precedent_citations: ['Golaknath v. State of Punjab'],
    relevance_score: 0.98
  },
  {
    chunk_id: '2',
    case_name: 'Maneka Gandhi v. Union of India',
    court: 'Supreme Court of India',
    year: 1978,
    segment_label: 'RatioOfTheDecision',
    raw_text: 'The expression "personal liberty" in Article 21 is of the widest amplitude and it covers a variety of rights which go to constitute the personal liberty of man. Any law depriving a person of personal liberty must not only follow a procedure established by law but such procedure must be reasonable, fair and just.',
    page_number: 12,
    statute_tags: ['Constitution Article 21', 'Article 14', 'Article 19'],
    precedent_citations: ['A.K. Gopalan v. State of Madras'],
    relevance_score: 0.95
  },
  {
    chunk_id: '3',
    case_name: 'Arnesh Kumar v. State of Bihar',
    court: 'Supreme Court of India',
    year: 2014,
    segment_label: 'FinalDecision',
    raw_text: 'We direct that the police officers shall not arrest the accused unnecessarily and the Magistrate shall not authorize detention casually and mechanically. In all cases where the offense is punishable with imprisonment for a term which may be less than seven years, the arrest may be made only if conditions under Section 41 of Cr.PC are satisfied.',
    page_number: 8,
    statute_tags: ['CrPC Section 41', 'IPC Section 498A'],
    precedent_citations: [],
    relevance_score: 0.92
  }
];

const ROLE_COLORS: Record<string, string> = {
  RatioOfTheDecision: 'bg-indigo-50 text-indigo-700 border-indigo-200 ring-indigo-500/10',
  FinalDecision: 'bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-500/10',
  Statute: 'bg-purple-50 text-purple-700 border-purple-200 ring-purple-500/10',
  Argument: 'bg-amber-50 text-amber-700 border-amber-200 ring-amber-500/10',
  Fact: 'bg-slate-50 text-slate-700 border-slate-200 ring-slate-500/10',
  Precedent: 'bg-orange-50 text-orange-700 border-orange-200 ring-orange-500/10',
  RulingByLowerCourt: 'bg-rose-50 text-rose-700 border-rose-200 ring-rose-500/10',
};

// Define History Item Type
interface HistoryItem {
  query: string;
  timestamp: string;
}

export default function LegalSearchApp() {
  const [query, setQuery] = useState('');
  const [selectedResult, setSelectedResult] = useState(MOCK_RESULTS[0]);
  const [isSearching, setIsSearching] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [searchHistory, setSearchHistory] = useState<HistoryItem[]>([]);
  const router = useRouter();
  const supabase = createClient();

  // Authentication Check
  useEffect(() => {
    async function getUser() {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        router.push('/login');
      } else {
        setUser(user);
        fetchHistory(user); // Fetch history
      }
    }
    getUser();
  }, [router, supabase.auth]);

  async function fetchHistory(user: any) {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const response = await fetch('http://localhost:8000/api/search/history', {
        headers: { 'Authorization': `Bearer ${session?.access_token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setSearchHistory(data);
      }
    } catch (err) {
      console.error('History fetch error:', err);
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setIsSearching(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const response = await fetch(`http://localhost:8000/api/search?query=${encodeURIComponent(query)}`, {
        headers: { 'Authorization': `Bearer ${session?.access_token}` }
      });

      if (response.ok) {
        const data = await response.json();
        console.log('Search results:', data);
        fetchHistory(user); // Refresh history
      }
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setIsSearching(false);
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
                  onClick={() => {
                    setQuery(item.query);
                    handleSearch({ preventDefault: () => {} } as any);
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-lg transition-all truncate"
                >
                  <Clock className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">{item.query}</span>
                </button>
              ))}
            </nav>
          </div>

          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">Refinement</h3>
              <button className="text-[10px] font-bold text-blue-600 uppercase">Clear</button>
            </div>
            <div className="space-y-5">
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-slate-700 ml-1">Jurisdiction</label>
                <select className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs font-semibold focus:ring-4 focus:ring-blue-500/5 focus:border-blue-500 transition-all outline-none appearance-none cursor-pointer">
                  <option>Supreme Court of India</option>
                  <option>All High Courts</option>
                  <option>Delhi High Court</option>
                </select>
              </div>
              
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-slate-700 ml-1">Role Hierarchy</label>
                <div className="grid grid-cols-1 gap-1.5">
                  {['Ratio Decidendi', 'Statutory Context', 'Precedential Value'].map(role => (
                    <label key={role} className="flex items-center gap-3 px-3 py-2.5 rounded-xl border border-slate-100 hover:bg-slate-50 cursor-pointer transition-all">
                      <input type="checkbox" className="w-4 h-4 rounded-md border-slate-300 text-blue-600 focus:ring-blue-500/20" />
                      <span className="text-xs font-semibold text-slate-600">{role}</span>
                    </label>
                  ))}
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
                <button className="bg-blue-600 hover:bg-blue-700 text-white p-2 rounded-xl transition-all shadow-lg shadow-blue-500/20 active:scale-95">
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
              <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">
                Search Latency: 24ms
              </p>
            </div>

            {isSearching ? (
              <div className="space-y-6">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-44 bg-white/60 border border-slate-200 rounded-3xl animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="space-y-6">
                {MOCK_RESULTS.map((result) => (
                  <div
                    key={result.chunk_id}
                    onClick={() => setSelectedResult(result)}
                    className={cn(
                      "group p-6 rounded-[32px] border transition-all cursor-pointer relative overflow-hidden",
                      selectedResult?.chunk_id === result.chunk_id 
                        ? "bg-white border-blue-500 shadow-2xl shadow-blue-500/10 ring-1 ring-blue-500" 
                        : "bg-white/70 border-slate-200/80 hover:bg-white hover:border-slate-300 hover:shadow-xl hover:shadow-slate-200/40"
                    )}
                  >
                    {/* Relevance bar */}
                    <div className="absolute top-0 left-0 bottom-0 w-1 bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                    
                    <div className="flex justify-between items-start gap-4 mb-4">
                      <div className="space-y-1">
                        <h4 className="font-extrabold text-lg text-slate-900 leading-tight group-hover:text-blue-600 transition-colors">
                          {result.case_name}
                        </h4>
                        <div className="flex items-center gap-3">
                           <span className="text-[11px] font-bold text-blue-600 uppercase tracking-widest">{result.court}</span>
                           <span className="w-1 h-1 bg-slate-300 rounded-full" />
                           <span className="text-[11px] font-bold text-slate-400">{result.year}</span>
                        </div>
                      </div>
                      <div className={cn(
                        "px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-[0.1em] border ring-1",
                        ROLE_COLORS[result.segment_label]
                      )}>
                        {result.segment_label.replace(/([A-Z])/g, ' $1').trim()}
                      </div>
                    </div>
                    
                    <p className="text-sm text-slate-600 font-medium leading-[1.7] mb-6 line-clamp-3">
                      {result.raw_text}
                    </p>

                    <div className="flex flex-wrap gap-2">
                      {result.statute_tags.map(tag => (
                        <div key={tag} className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 text-slate-600 text-[10px] font-bold rounded-xl border border-slate-200/60 group-hover:bg-blue-50/50 group-hover:border-blue-100 transition-all">
                          <FileText className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-500" />
                          {tag}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* RIGHT PANE - JUDGMENT READER */}
      <aside className="w-[480px] border-l border-slate-200 bg-white flex flex-col shrink-0 relative z-30 shadow-[-10px_0_30px_rgba(0,0,0,0.02)]">
        {selectedResult ? (
          <>
            <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-white/80 backdrop-blur-md sticky top-0 z-10">
              <h3 className="font-extrabold text-slate-900 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-blue-600" /> Analysis
              </h3>
              <div className="flex gap-2">
                <button className="p-2 hover:bg-slate-50 rounded-lg transition-colors border border-slate-100">
                  <ExternalLink className="w-4 h-4 text-slate-400" />
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto px-8 py-10 space-y-10">
              <div className="space-y-4">
                <div className="space-y-1">
                  <p className="text-[10px] font-black text-blue-600 uppercase tracking-[0.2em]">Judgment Extract</p>
                  <h2 className="text-2xl font-black leading-tight text-slate-900 tracking-tight italic">
                    “{selectedResult.case_name}”
                  </h2>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="text-[11px] bg-slate-900 text-white px-3 py-1 rounded-lg font-bold">
                    EST. {selectedResult.year}
                  </span>
                  <span className="text-[11px] bg-blue-50 text-blue-700 px-3 py-1 rounded-lg font-bold border border-blue-100">
                    Paragraph 204
                  </span>
                  <span className="text-[11px] bg-slate-50 text-slate-500 px-3 py-1 rounded-lg font-bold border border-slate-100">
                    Pg. {selectedResult.page_number}
                  </span>
                </div>
              </div>

              <div className="relative">
                <div className="absolute -left-6 top-0 bottom-0 w-1 bg-blue-600/20 rounded-full" />
                <div className="flex items-center gap-2 mb-4">
                   <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                   <span className="text-[11px] font-black uppercase tracking-[0.2em] text-blue-600">
                     Core Reasoning
                   </span>
                </div>
                <p className="text-slate-800 leading-[1.8] text-[17px] font-serif font-medium selection:bg-blue-200">
                  {selectedResult.raw_text}
                </p>
              </div>

              {selectedResult.statute_tags.length > 0 && (
                <div className="space-y-4">
                  <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2">
                    <Info className="w-3.5 h-3.5" /> Contextual Landmarks
                  </h4>
                  <div className="grid gap-2">
                    {selectedResult.statute_tags.map(tag => (
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

              <button className="w-full py-4 bg-slate-900 text-white rounded-2xl font-bold text-sm shadow-2xl shadow-slate-900/20 hover:bg-slate-800 transition-all flex items-center justify-center gap-3 group active:scale-[0.98]">
                <FileText className="w-4 h-4 group-hover:rotate-12 transition-transform" /> 
                Open Verified Judgment
              </button>
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

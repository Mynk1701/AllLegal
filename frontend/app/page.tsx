// Public marketing landing at `/`. Guests see this; middleware.ts redirects
// already-authed users straight to /search, so this never renders for them.
// Server component — it's just links, no client state. The brand language
// mirrors the login page's left panel so the two feel like one product.

import Link from 'next/link';
import { Scale, Search, ShieldCheck, Zap, ArrowRight } from 'lucide-react';

const FEATURES = [
  { Icon: Search, title: 'Semantic search', body: 'Meaning-based retrieval across 26k+ Supreme Court judgments — not keyword matching.' },
  { Icon: ShieldCheck, title: 'Verified data', body: 'Sourced from official SC/HC records, with citations, benches and outcomes extracted.' },
  { Icon: Zap, title: 'Built for advocates', body: 'Filter by court, statute, section and outcome. Save cases into matters as you research.' },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0F172A] text-white font-sans relative overflow-hidden">
      {/* ambient glow */}
      <div className="absolute top-0 right-0 -translate-y-1/3 translate-x-1/4 w-[700px] h-[700px] bg-blue-600/15 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-0 left-0 translate-y-1/3 -translate-x-1/4 w-[700px] h-[700px] bg-purple-600/10 rounded-full blur-[140px] pointer-events-none" />

      <div className="relative z-10 max-w-6xl mx-auto px-6">
        {/* NAV */}
        <header className="flex items-center justify-between py-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600 rounded-lg shadow-lg shadow-blue-500/20">
              <Scale className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight">AllLegal</span>
          </div>
          <nav className="flex items-center gap-3">
            <Link
              href="/login"
              className="px-4 py-2 text-sm font-bold text-slate-300 hover:text-white transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="px-4 py-2 text-sm font-bold bg-blue-600 hover:bg-blue-700 rounded-xl shadow-lg shadow-blue-500/20 transition-all active:scale-95"
            >
              Get started
            </Link>
          </nav>
        </header>

        {/* HERO */}
        <section className="pt-20 pb-24 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-8 rounded-full bg-white/5 border border-white/10 text-xs font-bold text-slate-300">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Legal research for Indian advocates
          </div>

          <h1 className="text-5xl sm:text-6xl font-extrabold leading-[1.05] tracking-tight mb-6">
            Justice, accelerated by <span className="text-blue-400">intelligence.</span>
          </h1>

          <p className="text-lg text-slate-400 leading-relaxed mb-10 max-w-2xl">
            Search 26,000+ Supreme Court judgments by meaning, not keywords. Filter by court,
            statute and outcome, then organise the cases that matter into your own matters.
          </p>

          <div className="flex flex-wrap items-center gap-4">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 px-6 py-3.5 text-sm font-bold bg-blue-600 hover:bg-blue-700 rounded-xl shadow-xl shadow-blue-500/25 transition-all active:scale-[0.98]"
            >
              Get started free <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 px-6 py-3.5 text-sm font-bold border border-white/15 hover:bg-white/5 rounded-xl transition-all"
            >
              Sign in
            </Link>
          </div>
        </section>

        {/* FEATURES */}
        <section className="grid md:grid-cols-3 gap-5 pb-24">
          {FEATURES.map(({ Icon, title, body }) => (
            <div
              key={title}
              className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm"
            >
              <div className="p-2 w-fit bg-blue-600/20 rounded-lg mb-4">
                <Icon className="w-5 h-5 text-blue-400" />
              </div>
              <h3 className="font-bold mb-1.5">{title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{body}</p>
            </div>
          ))}
        </section>

        {/* FOOTER */}
        <footer className="py-8 border-t border-white/10 text-sm text-slate-500">
          © 2026 AllLegal Intelligence Systems Pvt Ltd.
        </footer>
      </div>
    </div>
  );
}

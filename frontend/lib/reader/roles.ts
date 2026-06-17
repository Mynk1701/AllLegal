// Chunk rhetorical-role presentation. Extracted from app/page.tsx so the search
// UI and the PDF reader (hover chunk-type bar) share one source of truth.

/** Tailwind badge classes per rhetorical role (background/text/border/ring). */
export const ROLE_COLORS: Record<string, string> = {
  RatioOfTheDecision: 'bg-indigo-50 text-indigo-700 border-indigo-200 ring-indigo-500/10',
  'Ratio of the decision': 'bg-indigo-50 text-indigo-700 border-indigo-200 ring-indigo-500/10',
  FinalDecision: 'bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-500/10',
  'Ruling by Present Court': 'bg-emerald-50 text-emerald-700 border-emerald-200 ring-emerald-500/10',
  Statute: 'bg-purple-50 text-purple-700 border-purple-200 ring-purple-500/10',
  Argument: 'bg-amber-50 text-amber-700 border-amber-200 ring-amber-500/10',
  Fact: 'bg-slate-50 text-slate-700 border-slate-200 ring-slate-500/10',
  Facts: 'bg-slate-50 text-slate-700 border-slate-200 ring-slate-500/10',
  Precedent: 'bg-orange-50 text-orange-700 border-orange-200 ring-orange-500/10',
  RulingByLowerCourt: 'bg-rose-50 text-rose-700 border-rose-200 ring-rose-500/10',
  'Ruling by Lower Court': 'bg-rose-50 text-rose-700 border-rose-200 ring-rose-500/10',
};

/** Friendly display names; falls back to the raw role when unmapped. */
export const ROLE_DISPLAY_NAMES: Record<string, string> = {
  RatioOfTheDecision: 'Ratio Decidendi',
  'Ratio of the decision': 'Ratio Decidendi',
  FinalDecision: 'Final Order',
  'Ruling by Present Court': 'Final Order',
  RulingByLowerCourt: 'Lower Court Ruling',
  'Ruling by Lower Court': 'Lower Court Ruling',
};

export function roleLabel(role?: string | null): string {
  if (!role) return 'Passage';
  return ROLE_DISPLAY_NAMES[role] ?? role;
}

export function roleBadgeClass(role?: string | null): string {
  return (role && ROLE_COLORS[role]) || 'bg-slate-50 text-slate-600 border-slate-200 ring-slate-500/10';
}

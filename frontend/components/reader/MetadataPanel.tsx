'use client';

// Right-hand panel: all the extracted metadata for the open case, available
// alongside the PDF. Pure presentational from CaseDetail.

import { FileText, Scale, Users, Gavel, Link2 } from 'lucide-react';
import type { CaseDetail } from '@/lib/reader/types';

function parseVerdict(verdict?: string | null): string[] {
  if (!verdict) return [];
  try {
    const parsed = JSON.parse(verdict);
    return Array.isArray(parsed) ? parsed : [String(parsed)];
  } catch {
    return [String(verdict)];
  }
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h4 className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
        {icon}
        {title}
      </h4>
      {children}
    </div>
  );
}

export default function MetadataPanel({ caseDetail }: { caseDetail: CaseDetail }) {
  const verdicts = parseVerdict(caseDetail.verdict);
  const tags = caseDetail.sections_cited.length > 0 ? caseDetail.sections_cited : caseDetail.acts_cited;

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-white px-7 py-8">
      <div className="space-y-2">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-blue-600">Judgment</p>
        <h2 className="text-xl font-black leading-tight tracking-tight text-slate-900">{caseDetail.case_name}</h2>
        <div className="flex flex-wrap gap-2 pt-1">
          {caseDetail.citation && (
            <span className="rounded-lg bg-slate-900 px-3 py-1 text-[11px] font-bold text-white">{caseDetail.citation}</span>
          )}
          {caseDetail.court && (
            <span className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-1 text-[11px] font-bold text-blue-700">
              {caseDetail.court}
            </span>
          )}
          {caseDetail.year && (
            <span className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-1 text-[11px] font-bold text-slate-500">
              {caseDetail.year}
            </span>
          )}
        </div>
      </div>

      <div className="mt-8 space-y-8">
        {verdicts.length > 0 && (
          <Section title="Outcome" icon={<Gavel className="h-3.5 w-3.5" />}>
            <div className="flex flex-wrap gap-2">
              {verdicts.map((v) => (
                <span key={v} className="rounded-md border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-700">
                  {v}
                </span>
              ))}
            </div>
          </Section>
        )}

        <Section title="Bench" icon={<Users className="h-3.5 w-3.5" />}>
          <p className="text-sm font-semibold text-slate-700">
            {caseDetail.bench.length > 0 ? caseDetail.bench.join(', ') : `${caseDetail.bench_strength ?? 'Unknown'} judge(s)`}
          </p>
        </Section>

        {tags.length > 0 && (
          <Section title={caseDetail.sections_cited.length > 0 ? 'Sections cited' : 'Acts cited'} icon={<FileText className="h-3.5 w-3.5" />}>
            <div className="flex flex-wrap gap-2">
              {tags.map((t) => (
                <span key={t} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-bold text-slate-600">
                  <Scale className="h-3 w-3 text-slate-400" />
                  {t}
                </span>
              ))}
            </div>
          </Section>
        )}

        {caseDetail.cites.length > 0 && (
          <Section title="Precedents cited" icon={<Link2 className="h-3.5 w-3.5" />}>
            <div className="space-y-1.5">
              {caseDetail.cites.map((c, i) => (
                <div key={`${c.cited_canonical_key ?? 'cite'}-${i}`} className="rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2 text-[11px] font-semibold text-slate-600">
                  {c.cited_canonical_key ?? 'Unknown citation'}
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

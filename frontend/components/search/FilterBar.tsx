'use client';

// The query-bar filter strip. Everything lives on the bar as a pill — no
// drawer — because Acts and Sections are the filters lawyers reach for most:
//
//   Acts · Sections (once an act is picked) · Jurisdiction · Outcome ·
//   Case Type · Bench (slider) · Year (slider)
//
// Checkbox facets get a type-to-filter box once the list is long enough to
// scroll; Bench and Year are range sliders. Active selections render as
// removable chips below the bar.
//
// Controlled component: it never owns filter state. Every change calls
// onChange(next) with the FULL next filter set. The page STAGES that (updates
// state only) — the search runs on query-bar submit, not on filter change.

import { useEffect, useRef, useState } from 'react';
import {
  ChevronDown, X, Search, SlidersHorizontal,
  FileText, ListTree, Landmark, Gavel, Tag, Users, Calendar,
} from 'lucide-react';
import { clsx } from 'clsx';
import type { Facets, FacetValue } from '@/types/legal';
import type { SearchFilters } from '@/lib/search';
import RangeSlider from './RangeSlider';

// Re-exported so existing importers (`@/components/search/FilterBar`) keep working;
// the canonical definition now lives in lib/search.
export type { SearchFilters };

type CheckboxField = 'acts_cited' | 'court' | 'verdict' | 'case_type';
type IconType = typeof FileText;

const titleCase = (s: string) =>
  s.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());

const judges = (n: number | string) => `${n} ${String(n) === '1' ? 'Judge' : 'Judges'}`;

export default function FilterBar({
  facets,
  filters,
  onChange,
  onClearAll,
}: {
  facets: Facets | null;
  filters: SearchFilters;
  onChange: (next: SearchFilters) => void;
  onClearAll: () => void;
}) {
  const [openPill, setOpenPill] = useState<string | null>(null);
  const barRef = useRef<HTMLDivElement>(null);

  // Close any open popover on outside click / Escape.
  useEffect(() => {
    if (!openPill) return;
    const onDown = (e: MouseEvent) => {
      if (barRef.current && !barRef.current.contains(e.target as Node)) setOpenPill(null);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpenPill(null);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [openPill]);

  const labelFor = (field: keyof Facets, value: string | number) => {
    const opt = (facets?.[field] as FacetValue[] | undefined)?.find(
      (o) => String(o.value) === String(value),
    );
    return opt?.label || titleCase(String(value));
  };

  // ---- mutations (all produce a full next filter set) ----
  const toggleField = (field: CheckboxField, value: string) => {
    const cur = (filters[field] as string[] | undefined) ?? [];
    onChange({
      ...filters,
      [field]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value],
    });
  };

  // Removing an act drops the sections that belonged to it, atomically.
  const toggleAct = (value: string) => {
    const cur = filters.acts_cited ?? [];
    const has = cur.includes(value);
    onChange({
      ...filters,
      acts_cited: has ? cur.filter((a) => a !== value) : [...cur, value],
      sections_cited: has
        ? (filters.sections_cited ?? []).filter((s) => !String(s).startsWith(`${value} s.`))
        : (filters.sections_cited ?? []),
    });
  };

  const toggleSection = (value: string) => {
    const cur = filters.sections_cited ?? [];
    onChange({
      ...filters,
      sections_cited: cur.includes(value) ? cur.filter((s) => s !== value) : [...cur, value],
    });
  };

  // ---- derived: sections cascade ----
  const selectedActs = filters.acts_cited ?? [];
  const sectionsForSelectedActs = (facets?.sections_cited ?? []).filter((o) =>
    selectedActs.some((act) => String(o.value).startsWith(`${act} s.`)),
  );

  // ---- derived: bench slider ----
  const benchValues = (facets?.bench_strength ?? [])
    .map((o) => Number(o.value))
    .filter((n) => !Number.isNaN(n))
    .sort((a, b) => a - b);
  const benchMin = benchValues[0];
  const benchMax = benchValues[benchValues.length - 1];
  const benchSel = (filters.bench_strength ?? []).map(Number).filter((n) => !Number.isNaN(n));
  const benchLo = benchSel.length ? Math.min(...benchSel) : benchMin;
  const benchHi = benchSel.length ? Math.max(...benchSel) : benchMax;
  const benchActive = benchSel.length > 0;
  const setBench = ([lo, hi]: [number, number]) => {
    const sel = benchValues.filter((v) => v >= lo && v <= hi);
    const isFull = sel.length === benchValues.length;
    onChange({ ...filters, bench_strength: isFull ? [] : sel.map(String) });
  };

  // ---- derived: year slider ----
  const yMin = facets?.year_range?.min ?? null;
  const yMax = facets?.year_range?.max ?? null;
  const yearActive =
    (filters.year_from != null && filters.year_from !== '') ||
    (filters.year_to != null && filters.year_to !== '');
  const yLo = filters.year_from != null && filters.year_from !== '' ? Number(filters.year_from) : yMin ?? 0;
  const yHi = filters.year_to != null && filters.year_to !== '' ? Number(filters.year_to) : yMax ?? 0;
  const setYear = ([lo, hi]: [number, number]) => {
    const isFull = lo === yMin && hi === yMax;
    onChange({ ...filters, year_from: isFull ? undefined : lo, year_to: isFull ? undefined : hi });
  };

  // ---- chips ----
  const chips: { label: string; remove: () => void }[] = [];
  (filters.acts_cited ?? []).forEach((v) =>
    chips.push({ label: labelFor('acts_cited', v), remove: () => toggleAct(v) }),
  );
  (filters.sections_cited ?? []).forEach((v) =>
    chips.push({ label: labelFor('sections_cited', v), remove: () => toggleSection(v) }),
  );
  (filters.court ?? []).forEach((v) =>
    chips.push({ label: labelFor('court', v), remove: () => toggleField('court', v) }),
  );
  (filters.verdict ?? []).forEach((v) =>
    chips.push({ label: labelFor('verdict', v), remove: () => toggleField('verdict', v) }),
  );
  (filters.case_type ?? []).forEach((v) =>
    chips.push({ label: labelFor('case_type', v), remove: () => toggleField('case_type', v) }),
  );
  if (benchActive) {
    chips.push({
      label: benchLo === benchHi ? judges(benchLo) : `${benchLo}–${benchHi} Judges`,
      remove: () => onChange({ ...filters, bench_strength: [] }),
    });
  }
  if (yearActive) {
    chips.push({
      label: `${yLo}–${yHi}`,
      remove: () => onChange({ ...filters, year_from: undefined, year_to: undefined }),
    });
  }

  const toggleOpen = (key: string) => setOpenPill((o) => (o === key ? null : key));

  return (
    <div ref={barRef}>
      <div className="flex flex-wrap items-center gap-2 p-2 rounded-2xl bg-white/70 border border-slate-200/70 shadow-sm shadow-slate-200/30">
        <span className="hidden md:flex items-center gap-1.5 pl-2 pr-1 text-[11px] font-bold text-slate-400 uppercase tracking-wide shrink-0">
          <SlidersHorizontal className="w-4 h-4" /> Filters
        </span>

        {/* ACTS — up front */}
        {(facets?.acts_cited?.length ?? 0) > 0 && (
          <Pill
            Icon={FileText}
            label="Acts"
            count={filters.acts_cited?.length ?? 0}
            open={openPill === 'acts'}
            onClick={() => toggleOpen('acts')}
          >
            <FacetCheckList
              options={facets!.acts_cited}
              selected={selectedActs}
              format={(o) => o.label || titleCase(String(o.value))}
              onToggle={toggleAct}
            />
          </Pill>
        )}

        {/* SECTIONS — appears once an act is selected, scoped to it */}
        {selectedActs.length > 0 && (
          <Pill
            Icon={ListTree}
            label="Sections"
            count={filters.sections_cited?.length ?? 0}
            open={openPill === 'sections'}
            onClick={() => toggleOpen('sections')}
          >
            {sectionsForSelectedActs.length === 0 ? (
              <p className="text-[11px] text-slate-400 italic px-2 py-2">
                No cited sections for the selected act(s).
              </p>
            ) : (
              <FacetCheckList
                options={sectionsForSelectedActs}
                selected={filters.sections_cited ?? []}
                format={(o) => o.label || String(o.value)}
                onToggle={toggleSection}
              />
            )}
          </Pill>
        )}

        {/* JURISDICTION */}
        {(facets?.court?.length ?? 0) > 0 && (
          <Pill
            Icon={Landmark}
            label="Jurisdiction"
            count={filters.court?.length ?? 0}
            open={openPill === 'court'}
            onClick={() => toggleOpen('court')}
          >
            <FacetCheckList
              options={facets!.court}
              selected={filters.court ?? []}
              format={(o) => o.label || titleCase(String(o.value))}
              onToggle={(v) => toggleField('court', v)}
            />
          </Pill>
        )}

        {/* OUTCOME */}
        {(facets?.verdict?.length ?? 0) > 0 && (
          <Pill
            Icon={Gavel}
            label="Outcome"
            count={filters.verdict?.length ?? 0}
            open={openPill === 'verdict'}
            onClick={() => toggleOpen('verdict')}
          >
            <FacetCheckList
              options={facets!.verdict}
              selected={filters.verdict ?? []}
              format={(o) => o.label || titleCase(String(o.value))}
              onToggle={(v) => toggleField('verdict', v)}
            />
          </Pill>
        )}

        {/* CASE TYPE — only once the pipeline populates it */}
        {(facets?.case_type?.length ?? 0) > 0 && (
          <Pill
            Icon={Tag}
            label="Case Type"
            count={filters.case_type?.length ?? 0}
            open={openPill === 'case_type'}
            onClick={() => toggleOpen('case_type')}
          >
            <FacetCheckList
              options={facets!.case_type}
              selected={filters.case_type ?? []}
              format={(o) => o.label || titleCase(String(o.value))}
              onToggle={(v) => toggleField('case_type', v)}
            />
          </Pill>
        )}

        {/* BENCH — slider */}
        {benchValues.length > 1 && (
          <Pill
            Icon={Users}
            label="Bench"
            count={benchActive ? 1 : 0}
            badge={benchActive ? (benchLo === benchHi ? String(benchLo) : `${benchLo}–${benchHi}`) : undefined}
            open={openPill === 'bench'}
            onClick={() => toggleOpen('bench')}
            width="w-72"
          >
            <RangeSlider
              min={benchMin}
              max={benchMax}
              value={[benchLo, benchHi]}
              onChange={setBench}
              format={(n) => judges(n)}
            />
          </Pill>
        )}

        {/* YEAR — slider */}
        {yMin != null && yMax != null && yMax > yMin && (
          <Pill
            Icon={Calendar}
            label="Year"
            count={yearActive ? 1 : 0}
            badge={yearActive ? `${yLo}–${yHi}` : undefined}
            open={openPill === 'year'}
            onClick={() => toggleOpen('year')}
            width="w-72"
          >
            <RangeSlider min={yMin} max={yMax} value={[yLo, yHi]} onChange={setYear} />
          </Pill>
        )}
      </div>

      {/* ACTIVE CHIPS */}
      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mt-3">
          {chips.map((c, i) => (
            <button
              key={`${c.label}-${i}`}
              onClick={c.remove}
              className="group flex items-center gap-1.5 pl-3 pr-2 py-1.5 rounded-lg bg-blue-50 text-blue-700 border border-blue-100 text-xs font-bold hover:bg-blue-100 transition-colors"
            >
              <span className="truncate max-w-[220px]">{c.label}</span>
              <X className="w-3.5 h-3.5 text-blue-400 group-hover:text-blue-600" />
            </button>
          ))}
          <button
            onClick={onClearAll}
            className="text-[11px] font-bold text-slate-400 hover:text-rose-600 uppercase tracking-wide px-1 transition-colors"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
}

function Pill({
  Icon,
  label,
  count,
  badge,
  open,
  onClick,
  width = 'w-64',
  children,
}: {
  Icon: IconType;
  label: string;
  count: number;
  badge?: string;
  open: boolean;
  onClick: () => void;
  width?: string;
  children: React.ReactNode;
}) {
  const active = count > 0;
  return (
    <div className="relative">
      <button
        type="button"
        onClick={onClick}
        aria-expanded={open}
        className={clsx(
          'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold border transition-all',
          active
            ? 'bg-blue-600 text-white border-blue-600 shadow-lg shadow-blue-500/20'
            : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300 hover:bg-slate-50',
        )}
      >
        <Icon className="w-4 h-4 shrink-0" />
        {label}
        {active && (
          <span className="px-1.5 py-0.5 rounded-md text-[10px] leading-none bg-white/20">
            {badge ?? count}
          </span>
        )}
        <ChevronDown className={clsx('w-4 h-4 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div
          className={clsx(
            'absolute left-0 top-full mt-2 z-50 rounded-2xl bg-white border border-slate-200 shadow-2xl shadow-slate-300/40 p-3 animate-in fade-in slide-in-from-top-1 duration-150',
            width,
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}

function FacetCheckList({
  options,
  selected,
  format,
  onToggle,
}: {
  options: FacetValue[];
  selected: string[];
  format: (o: FacetValue) => string;
  onToggle: (value: string) => void;
}) {
  const [q, setQ] = useState('');
  // Type-to-filter once the list is long enough to scroll (substring on label).
  const showSearch = options.length > 7;
  const visible = q
    ? options.filter((o) => format(o).toLowerCase().includes(q.toLowerCase()))
    : options;

  return (
    <div className="flex flex-col gap-1">
      {showSearch && (
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <input
            autoFocus
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Type to filter…"
            className="w-full pl-8 pr-2 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
      )}
      <div className="max-h-60 overflow-y-auto flex flex-col gap-0.5">
        {visible.map((o) => {
          const val = String(o.value);
          const checked = selected.includes(val);
          return (
            <label
              key={val}
              className="flex items-center justify-between gap-3 px-2.5 py-2 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors"
            >
              <span className="flex items-center gap-2.5 min-w-0">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => onToggle(val)}
                  className="w-4 h-4 rounded-md border-slate-300 text-blue-600 focus:ring-blue-500/20 shrink-0"
                />
                <span className="text-xs font-semibold text-slate-700 truncate">{format(o)}</span>
              </span>
              <span className="text-[10px] font-bold text-slate-400 shrink-0">{o.count}</span>
            </label>
          );
        })}
        {visible.length === 0 && (
          <p className="text-[11px] text-slate-400 italic px-2 py-2">No matches.</p>
        )}
      </div>
    </div>
  );
}

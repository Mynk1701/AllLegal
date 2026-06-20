'use client';

// Dual-thumb range slider used by the Year and Bench filter pills. Two overlaid
// native range inputs (no extra dependency, keyboard-accessible); the filled
// track + thumb styling live in globals.css (.range-input). Controlled: emits
// the clamped [lo, hi] on every change.

interface RangeSliderProps {
  min: number;
  max: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
  format?: (n: number) => string;
}

export default function RangeSlider({ min, max, value, onChange, format }: RangeSliderProps) {
  const [lo, hi] = value;
  const span = max - min || 1;
  const loPct = ((lo - min) / span) * 100;
  const hiPct = ((hi - min) / span) * 100;
  const fmt = format ?? ((n: number) => String(n));

  return (
    <div className="px-1 pt-1">
      <div className="mb-3 flex items-center justify-between">
        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-bold text-slate-700">
          {fmt(lo)}
        </span>
        <span className="text-[11px] font-bold text-slate-400">to</span>
        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-bold text-slate-700">
          {fmt(hi)}
        </span>
      </div>

      <div className="relative h-5">
        <div className="absolute top-1/2 h-1.5 w-full -translate-y-1/2 rounded-full bg-slate-200" />
        <div
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-blue-600"
          style={{ left: `${loPct}%`, right: `${100 - hiPct}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          value={lo}
          aria-label="Minimum"
          onChange={(e) => onChange([Math.min(Number(e.target.value), hi), hi])}
          className="range-input absolute top-0 h-5 w-full"
        />
        <input
          type="range"
          min={min}
          max={max}
          value={hi}
          aria-label="Maximum"
          onChange={(e) => onChange([lo, Math.max(Number(e.target.value), lo)])}
          className="range-input absolute top-0 h-5 w-full"
        />
      </div>
    </div>
  );
}

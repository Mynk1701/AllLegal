'use client';

import * as React from 'react';

interface YearRangeSliderProps {
  min: number;
  max: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
}

/**
 * Lightweight dual-thumb range slider built on two overlaid native range
 * inputs — no extra dependency, fully keyboard-accessible. Styling for the
 * thumbs lives in globals.css (.range-thumb).
 */
export function YearRangeSlider({ min, max, value, onChange }: YearRangeSliderProps) {
  const [lo, hi] = value;
  const range = max - min || 1;
  const loPct = ((lo - min) / range) * 100;
  const hiPct = ((hi - min) / range) * 100;

  return (
    <div className="px-1">
      <div className="mb-3 flex items-center justify-between">
        <span className="nums rounded-md border border-border bg-card px-2 py-0.5 text-meta font-medium tabular-nums text-foreground shadow-hairline">
          {lo}
        </span>
        <span className="text-meta text-muted-foreground">to</span>
        <span className="nums rounded-md border border-border bg-card px-2 py-0.5 text-meta font-medium tabular-nums text-foreground shadow-hairline">
          {hi}
        </span>
      </div>

      <div className="relative h-5">
        <div className="absolute top-1/2 h-1 w-full -translate-y-1/2 rounded-full bg-muted" />
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-primary"
          style={{ left: `${loPct}%`, right: `${100 - hiPct}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          value={lo}
          aria-label="Earliest year"
          onChange={(e) => onChange([Math.min(Number(e.target.value), hi), hi])}
          className="range-thumb absolute top-0 h-5 w-full appearance-none bg-transparent"
        />
        <input
          type="range"
          min={min}
          max={max}
          value={hi}
          aria-label="Latest year"
          onChange={(e) => onChange([lo, Math.max(Number(e.target.value), lo)])}
          className="range-thumb absolute top-0 h-5 w-full appearance-none bg-transparent"
        />
      </div>
    </div>
  );
}

'use client';

import * as React from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface FacetOption {
  value: string;
  count?: number;
}
export interface Facet {
  label: string;
  options: FacetOption[];
}

export function FacetSection({
  facet,
  selected,
  onToggle,
  defaultOpen = true,
}: {
  facet: Facet;
  selected: string[];
  onToggle: (value: string) => void;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);

  return (
    <div className="border-b border-border py-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-md px-1 py-1 text-left text-meta font-semibold tracking-wide text-foreground uppercase transition-colors hover:text-primary"
      >
        {facet.label}
        <ChevronDown
          className={cn(
            'size-4 text-muted-foreground transition-transform',
            open && 'rotate-180',
          )}
        />
      </button>

      {open ? (
        <ul className="mt-1.5 flex flex-col gap-0.5">
          {facet.options.map((opt) => {
            const checked = selected.includes(opt.value);
            const disabled = opt.count === 0;
            return (
              <li key={opt.value}>
                <label
                  className={cn(
                    'group flex cursor-pointer items-center gap-2.5 rounded-md px-1.5 py-1.5 transition-colors',
                    disabled ? 'cursor-not-allowed opacity-40' : 'hover:bg-muted',
                  )}
                >
                  <input
                    type="checkbox"
                    className="peer sr-only"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => onToggle(opt.value)}
                  />
                  <span
                    aria-hidden
                    className={cn(
                      'grid size-4 shrink-0 place-items-center rounded-[5px] border transition-colors',
                      checked
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border bg-card group-hover:border-primary/50',
                    )}
                  >
                    {checked ? (
                      <svg viewBox="0 0 12 12" className="size-3" fill="none">
                        <path
                          d="M2.5 6.2l2.2 2.2 4.8-4.8"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    ) : null}
                  </span>
                  <span className="flex-1 truncate text-meta text-foreground">
                    {opt.value}
                  </span>
                  {typeof opt.count === 'number' ? (
                    <span className="nums shrink-0 text-caption tabular-nums text-muted-foreground">
                      {opt.count.toLocaleString('en-IN')}
                    </span>
                  ) : null}
                </label>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

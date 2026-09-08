'use client';

// Plan chip + "searches left this month" for the NavRail. Fetches billing/me on
// mount (client-side, mirroring how search/page.tsx reads the user) and, for
// metered tiers, shows an Upgrade link to /pricing. Styled for the dark rail.

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { clsx } from 'clsx';
import { getBilling } from '@/lib/api';
import { BILLING_CHANGED_EVENT, type Billing } from '@/lib/billing/types';

const TIER_LABEL: Record<string, string> = { free: 'Free', pro: 'Pro', internal: 'Internal' };

export default function BillingBadge({ collapsed }: { collapsed?: boolean }) {
  const [billing, setBilling] = useState<Billing | null>(null);

  useEffect(() => {
    let alive = true;
    const refresh = () =>
      getBilling()
        .then((b) => alive && setBilling(b))
        .catch(() => {});

    refresh(); // on mount
    // re-fetch whenever a search (or upgrade) reports usage may have changed
    window.addEventListener(BILLING_CHANGED_EVENT, refresh);
    return () => {
      alive = false;
      window.removeEventListener(BILLING_CHANGED_EVENT, refresh);
    };
  }, []);

  if (!billing) return null;

  const label = TIER_LABEL[billing.tier] ?? billing.tier;
  const unlimited = billing.searches_limit === null;
  const left = unlimited ? null : Math.max(0, billing.searches_limit! - billing.searches_used);
  const metered = left !== null;

  if (collapsed) {
    return (
      <div
        title={`${label}${metered ? ` · ${left} searches left` : ''}`}
        className={clsx(
          'w-9 h-9 rounded-xl flex items-center justify-center text-[11px] font-bold',
          billing.tier === 'pro'
            ? 'bg-blue-600 text-white'
            : billing.tier === 'internal'
              ? 'bg-emerald-600/80 text-white'
              : 'bg-white/10 text-slate-300',
        )}
      >
        {label.slice(0, 3)}
      </div>
    );
  }

  return (
    <div className="px-1 mb-3">
      <div className="flex items-center justify-between mb-2">
        <span
          className={clsx(
            'px-2 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wide',
            billing.tier === 'pro'
              ? 'bg-blue-600 text-white'
              : billing.tier === 'internal'
                ? 'bg-emerald-600/80 text-white'
                : 'bg-white/10 text-slate-300',
          )}
        >
          {label}
        </span>
        {metered && (
          <span className="text-[11px] font-semibold text-slate-400">
            {left} left
          </span>
        )}
      </div>
      {metered && (
        <Link
          href="/pricing"
          className="flex items-center justify-center gap-1.5 w-full px-3 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold transition-all active:scale-[0.98]"
        >
          <Sparkles className="w-3.5 h-3.5" /> Upgrade to Pro
        </Link>
      )}
    </div>
  );
}

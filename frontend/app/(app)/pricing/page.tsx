'use client';

// Pricing / upgrade page. Lives under the (app) group so it inherits the NavRail
// shell + proxy auth gating. "Upgrade" starts a Razorpay subscription on the
// backend, opens Razorpay Checkout, then polls billing/me until the webhook has
// flipped the account to Pro (the webhook — not this browser — is the source of
// truth for the tier change).

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Sparkles, Loader2 } from 'lucide-react';
import { getBilling, subscribe } from '@/lib/api';
import type { Billing } from '@/lib/billing/types';

// Display price only — the actual amount is set by the Razorpay plan (RAZORPAY_PLAN_ID).
const PRO_PRICE_LABEL = '₹500 / month';

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

function loadRazorpay(): Promise<NonNullable<typeof window.Razorpay>> {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve(window.Razorpay);
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = () => (window.Razorpay ? resolve(window.Razorpay) : reject(new Error('Razorpay failed to load')));
    script.onerror = () => reject(new Error('Razorpay failed to load'));
    document.body.appendChild(script);
  });
}

const FREE_FEATURES = ['15 searches / month', 'Full case reader & PDF', 'Groups & annotations', 'Search history'];
const PRO_FEATURES = ['Unlimited searches', 'Full case reader & PDF', 'Groups & annotations', 'Priority support'];

export default function PricingPage() {
  const router = useRouter();
  const [billing, setBilling] = useState<Billing | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [awaitingActivation, setAwaitingActivation] = useState(false);

  useEffect(() => {
    getBilling().then(setBilling).catch(() => {});
  }, []);

  const isPro = billing?.tier === 'pro' && billing?.searches_limit === null;
  const isInternal = billing?.tier === 'internal';

  // Poll after payment until the webhook upgrades the account, then send them back to search.
  async function pollUntilPro(attempts = 20) {
    for (let i = 0; i < attempts; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      try {
        const b = await getBilling();
        setBilling(b);
        if (b.tier === 'pro' && b.searches_limit === null) {
          setAwaitingActivation(false);
          router.push('/search');
          return;
        }
      } catch {
        /* keep polling */
      }
    }
    setAwaitingActivation(false);
    setError('Payment received — your Pro plan may take a moment to activate. Refresh shortly.');
  }

  async function handleUpgrade() {
    setBusy(true);
    setError(null);
    try {
      const { subscription_id, key_id } = await subscribe();
      const Razorpay = await loadRazorpay();
      const rzp = new Razorpay({
        key: key_id,
        subscription_id,
        name: 'Nirnay Legal',
        description: 'Pro — unlimited searches',
        theme: { color: '#2563eb' },
        handler: () => {
          // Payment submitted. The Razorpay webhook grants Pro server-side; poll for it.
          setAwaitingActivation(true);
          pollUntilPro();
        },
        modal: {
          ondismiss: () => setBusy(false),
        },
      });
      rzp.open();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start checkout');
      setBusy(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-8 py-12 relative z-10">
      <div className="max-w-4xl mx-auto">
        <header className="text-center mb-10">
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Plans & pricing</h1>
          <p className="text-base text-slate-500 font-medium mt-2">
            Search smarter. Upgrade for unlimited access.
          </p>
          {isInternal && (
            <p className="mt-4 inline-block px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-sm font-semibold">
              You're on the Internal plan — unlimited searches, comped.
            </p>
          )}
        </header>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Free */}
          <div className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
            <h2 className="text-lg font-black text-slate-900">Free</h2>
            <p className="mt-1 text-3xl font-black text-slate-900">₹0<span className="text-base font-semibold text-slate-400"> / month</span></p>
            <p className="mt-1 text-sm text-slate-500">Get started, resets monthly.</p>
            <ul className="mt-5 space-y-2.5">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-center gap-2.5 text-sm text-slate-700">
                  <Check className="w-4 h-4 text-slate-400 shrink-0" /> {f}
                </li>
              ))}
            </ul>
            <div className="mt-6 text-center text-sm font-semibold text-slate-400 py-2.5">
              {!isPro && !isInternal ? 'Your current plan' : 'Included'}
            </div>
          </div>

          {/* Pro */}
          <div className="rounded-2xl border-2 border-blue-600 bg-white p-7 shadow-xl shadow-blue-500/10 relative">
            <span className="absolute -top-3 left-7 px-2.5 py-1 rounded-full bg-blue-600 text-white text-[11px] font-bold uppercase tracking-wide">
              Recommended
            </span>
            <h2 className="text-lg font-black text-slate-900">Pro</h2>
            <p className="mt-1 text-3xl font-black text-slate-900">{PRO_PRICE_LABEL}</p>
            <p className="mt-1 text-sm text-slate-500">Unlimited searches for serious research.</p>
            <ul className="mt-5 space-y-2.5">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-center gap-2.5 text-sm text-slate-700">
                  <Check className="w-4 h-4 text-blue-600 shrink-0" /> {f}
                </li>
              ))}
            </ul>
            {isPro ? (
              <div className="mt-6 text-center text-sm font-bold text-blue-600 py-2.5">Your current plan</div>
            ) : isInternal ? (
              <div className="mt-6 text-center text-sm font-semibold text-slate-400 py-2.5">Not needed on Internal</div>
            ) : (
              <button
                onClick={handleUpgrade}
                disabled={busy || awaitingActivation}
                className="mt-6 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold transition-all active:scale-[0.98] disabled:opacity-60"
              >
                {busy || awaitingActivation ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> {awaitingActivation ? 'Activating…' : 'Starting…'}</>
                ) : (
                  <><Sparkles className="w-4 h-4" /> Upgrade to Pro</>
                )}
              </button>
            )}
          </div>
        </div>

        {error && (
          <p className="mt-6 text-center text-sm font-semibold text-rose-600">{error}</p>
        )}
      </div>
    </div>
  );
}

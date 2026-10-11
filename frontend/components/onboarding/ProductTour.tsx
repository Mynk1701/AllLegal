'use client';

// Guided tour for first-time users, driven by driver.js.
//
// Steps and copy live in lib/onboarding/config.ts — edit there, not here.
//
// SEEDED: starting the tour also runs a real search (the `onSeed` callback),
// because steps 2-5 highlight a result card, the filter bar and the analysis
// panel — none of which are in the DOM on an empty page. Running a search makes
// every later step point at something real, and demonstrates the product rather
// than describing it.
//
// We do NOT hand-roll waiting for those elements: driver.js's `waitForElement`
// watches the DOM with a MutationObserver and only blocks when the anchor is
// actually missing, which is exactly right here — the seed search round-trips to
// Render + OpenSearch (~1-3s warm, much slower on a Render cold start).
//
// "Seen" is owned by the PARENT and persisted per-user in Supabase
// user_metadata (see lib/onboarding/config.ts for why metadata and not a
// table). This component holds no data-layer concerns; it only reports that a
// tour started, via onMarkSeen.

import { useCallback, useEffect, useRef } from 'react';
import { HelpCircle } from 'lucide-react';
import { driver, type Driver } from 'driver.js';
import 'driver.js/dist/driver.css';
// Our overrides — must come AFTER driver's own stylesheet so they win.
import './tour.css';
import { TOUR_SEED_QUERY, TOUR_STEPS } from '@/lib/onboarding/config';

type Props = {
  /** Runs the seed search. The tour waits for its results via waitForElement. */
  onSeed: (query: string) => void;
  /** True once the page is interactive — gates the first-visit auto-start. */
  ready: boolean;
  /** Has THIS USER already seen the tour? (from user_metadata) */
  seen: boolean;
  /** Persist that the tour has been seen. Fire-and-forget; must not throw. */
  onMarkSeen: () => void;
};

export default function ProductTour({ onSeed, ready, seen, onMarkSeen }: Props) {
  const driverRef = useRef<Driver | null>(null);

  const start = useCallback(() => {
    driverRef.current?.destroy();

    const d = driver({
      showProgress: true,
      allowClose: true,
      overlayOpacity: 0.65,
      stagePadding: 6,
      stageRadius: 12,
      smoothScroll: true,
      // Scopes components/onboarding/tour.css to this instance.
      popoverClass: 'nirnay-tour',
      // Wait up to 20s for an anchor that isn't in the DOM yet (the seeded
      // search has to come back first). Costs nothing when the anchor is
      // already present — driver.js checks before it waits.
      waitForElement: 20000,
      // If an anchor never appears (search failed, zero results, markup moved),
      // skip that step instead of dead-ending the tour on a missing selector.
      skipMissingElement: true,
      doneBtnText: 'Start searching',
      nextBtnText: 'Next',
      prevBtnText: 'Back',
      closeBtnLabel: "Close — I'll explore on my own",
      steps: TOUR_STEPS.map((s) => ({
        element: s.element,
        popover: { title: s.title, description: s.description },
      })),
    });

    driverRef.current = d;
    // Starting counts as seen, not finishing: a mid-tour refresh should not
    // replay it from step 1. The trade-off is that someone interrupted at step
    // 2 is not re-offered it — they can reopen it from the Tour button.
    onMarkSeen();
    d.drive();

    // Seed immediately so steps 2-5 have anchors by the time the user clicks Next.
    onSeed(TOUR_SEED_QUERY);
  }, [onSeed, onMarkSeen]);

  // Keep the latest `start` reachable WITHOUT making it an effect dependency.
  // The parent passes inline callbacks, so `start` has a new identity on every
  // render. As a dependency it would re-run the effect below every render, and
  // each re-run's cleanup would clear the pending timer — so the tour could
  // never actually fire.
  const startRef = useRef(start);
  startRef.current = start;

  // Auto-start once for a user who has not seen it, after the page is interactive.
  //
  // The guard is set INSIDE the timer, not before it. Next.js enables React
  // Strict Mode by default on the App Router, which deliberately double-invokes
  // effects (mount -> cleanup -> mount). Claiming the guard up front meant the
  // cleanup cancelled the pending timer and the re-run then bailed on the
  // already-claimed guard, so the tour never fired in dev. Claiming it inside
  // lets the re-run reschedule, while still preventing a double start.
  //
  // Same reason the guard is a ref and not state: setting state here would
  // change a dependency and trigger the very cleanup that cancels the timer.
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (autoStartedRef.current || !ready || seen) return;
    const t = window.setTimeout(() => {
      if (autoStartedRef.current) return;
      autoStartedRef.current = true;
      startRef.current();
    }, 600); // let the first paint settle
    return () => window.clearTimeout(t);
  }, [ready, seen]);

  // Tear the overlay down on unmount, or it outlives a route change.
  useEffect(() => () => driverRef.current?.destroy(), []);

  return (
    <button
      type="button"
      onClick={start}
      title="Take a quick tour"
      className="flex items-center gap-1.5 shrink-0 px-3 py-2 rounded-xl text-xs font-bold text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition-colors"
    >
      <HelpCircle className="w-4 h-4" />
      <span className="hidden sm:inline">Tour</span>
    </button>
  );
}

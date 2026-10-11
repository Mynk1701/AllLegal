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

import { useCallback, useEffect, useRef } from 'react';
import { HelpCircle } from 'lucide-react';
import { driver, type Driver } from 'driver.js';
import 'driver.js/dist/driver.css';
// Our overrides — must come AFTER driver's own stylesheet so they win.
import './tour.css';
import { TOUR_SEEN_KEY, TOUR_SEED_QUERY, TOUR_STEPS } from '@/lib/onboarding/config';

// Private windows and "block site data" make localStorage throw on ACCESS, not
// just return null — so both of these need try/catch, not a null check.
//
// Survives a blocked store in memory instead. Returning `true` on throw (the
// obvious "don't nag them" reflex) is wrong: a private window is a genuine
// first visit and the single most likely place someone evaluates the product,
// so it must still get the tour. The module-level flag stops it re-showing on
// client-side navigation within the same session.
let seenThisSession = false;

function readSeen(): boolean {
  if (seenThisSession) return true;
  try {
    return window.localStorage.getItem(TOUR_SEEN_KEY) === '1';
  } catch {
    return false; // storage blocked -> treat as unseen, guard in memory
  }
}

function markSeen() {
  seenThisSession = true;
  try {
    window.localStorage.setItem(TOUR_SEEN_KEY, '1');
  } catch {
    /* storage blocked: the in-memory flag covers this session */
  }
}

type Props = {
  /** Runs the seed search. The tour waits for its results via waitForElement. */
  onSeed: (query: string) => void;
  /** True once the page is interactive — gates the first-visit auto-start. */
  ready: boolean;
};

export default function ProductTour({ onSeed, ready }: Props) {
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
      onDestroyed: markSeen,
    });

    driverRef.current = d;
    markSeen(); // starting counts as seen — a mid-tour refresh shouldn't restart it
    d.drive();

    // Seed immediately so steps 2-5 have anchors by the time the user clicks Next.
    onSeed(TOUR_SEED_QUERY);
  }, [onSeed]);

  // Keep the latest `start` reachable WITHOUT making it an effect dependency.
  // The parent passes `onSeed` as an inline arrow, so it — and therefore
  // `start` — has a new identity on every render. As a dependency it would
  // re-run the effect below every render, and each re-run's cleanup would clear
  // the pending timer, so the tour could never actually fire.
  const startRef = useRef(start);
  startRef.current = start;

  // Auto-start once per session for a first-time visitor, after the page is
  // interactive. Guarded by a ref, not state: setting state here would change a
  // dependency, and React would run this effect's cleanup — cancelling the very
  // timer it just scheduled. (That is exactly the bug this replaces.)
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (autoStartedRef.current || !ready) return;
    autoStartedRef.current = true;
    // Read storage here, not during render: localStorage does not exist during
    // prerender, and reading it in render would desync hydration.
    if (readSeen()) return;
    const t = window.setTimeout(() => startRef.current(), 600); // let first paint settle
    return () => window.clearTimeout(t);
  }, [ready]);

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

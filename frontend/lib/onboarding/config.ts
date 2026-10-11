// Onboarding config — EDIT THIS FILE to change the tour or the example queries.
// Nothing else needs touching: the empty state reads EXAMPLE_QUERIES and the
// tour reads TOUR_STEPS, both at render time.
//
// Why onboarding exists at all: our users come from Manupatra/SCC, which are
// boolean keyword engines. Their instinct is to type `438 CrPC`. The whole point
// of this product is that you can ask a QUESTION and get the paragraph that
// answers it — so the single most valuable thing onboarding can do is get them
// to run one natural-language query and see the passage come back. Everything
// else in the UI is self-evident once that lands.

/** One clickable example on the pre-first-search empty state. */
export type ExampleQuery = {
  /** The query actually sent to /api/search. Keep it a QUESTION, not keywords. */
  query: string;
  /** Short label under the question — the area of law, for scanning. */
  topic: string;
};

/**
 * Example questions for the empty state.
 *
 * Every one of these was run against the live corpus on 2026-10-11 and returned
 * real results (case counts in the comments). If you add one, SEARCH IT FIRST —
 * an example that returns nothing is worse than no example, because it reads as
 * "this product doesn't work" on a first impression.
 *
 * Phrased as full questions on purpose: the example is the lesson. A chip
 * reading "bail" would teach exactly the keyword habit we're trying to break.
 */
export const EXAMPLE_QUERIES: ExampleQuery[] = [
  // Verified against production 2026-10-11 — case count, and the top hit, which
  // is the thing a lawyer judges us on in the first five seconds:
  { query: 'What are the conditions for granting anticipatory bail?', topic: 'Criminal — bail' },
  // 341 cases · Sushila Aggarwal v. State (NCT of Delhi) — the Constitution Bench on s.438
  { query: 'When can specific performance of a contract be refused?', topic: 'Contract' },
  // 393 cases · Rojasara Ramjibhai Dahyabhai
  { query: 'What amounts to cruelty as a ground for divorce?', topic: 'Family' },
  // 329 cases · Gurbux Singh v. Harminder Kaur
  { query: 'Liability of a director for cheque dishonour under the NI Act', topic: 'Negotiable Instruments' },
  // 266 cases · Sunita Palita v. M/s Panchami — squarely on director liability
  { query: 'When is a dying declaration admissible as sole evidence?', topic: 'Evidence' },
  // 387 cases · Chirra Shivraj v. State of A.P.
  { query: 'Compensation principles in motor accident claims', topic: 'Motor Accident' },
  // 415 cases · Pappu Deo Yadav v. Naresh Kumar
];

/**
 * The query the guided tour runs on the user's behalf at step 1.
 *
 * The tour is SEEDED: steps 2-5 point at a result card, the filter bar, and the
 * analysis panel, none of which exist on an empty page. Running a real search
 * first gives every later step something real to highlight — and demonstrates
 * the product instead of describing it.
 *
 * Derived from EXAMPLE_QUERIES[0] rather than hardcoded, so the tour and the
 * empty state can never drift apart: reorder the examples and the seed follows.
 */
export const TOUR_SEED_QUERY = EXAMPLE_QUERIES[0].query;

/** A single tour step. `element` is a CSS selector, matched when the step runs. */
export type TourStep = {
  /** Selector for the element to highlight. Omit for a centered, unanchored step. */
  element?: string;
  title: string;
  description: string;
};

/**
 * The tour, in the order we want someone to actually use the platform:
 *   ask a question -> read the passage -> narrow it -> open the judgment -> save it
 *
 * Five steps, deliberately. Published guidance converges on 3-7 and reports
 * completion falling sharply beyond that: past ~7 people stop reading and click
 * Next to dismiss. History is intentionally NOT a step — it is self-explanatory
 * and low-stakes, and every extra step costs completion on the steps that matter.
 *
 * Every anchor is a `[data-tour="..."]` attribute in app/(app)/search/page.tsx.
 * If you retarget a step, grep for its data-tour value first: driver.js waits
 * `waitForElement` ms for a missing anchor and then SKIPS that step silently
 * (skipMissingElement), so a stale selector fails quietly rather than loudly.
 */
export const TOUR_STEPS: TourStep[] = [
  {
    element: '[data-tour="search-input"]',
    title: 'Ask it like a question',
    description:
      "Type what you actually want to know — <em>what are the conditions for anticipatory bail</em> — not <code>438 CrPC</code>. We search by meaning, so plain English works better than keywords. We've run one for you.",
  },
  {
    element: '[data-tour="result-passage"]',
    title: 'The paragraph, not just the case',
    description:
      'We return the passage that answers you, tagged by its role in the judgment — Facts, Ratio, Final Decision. Skim the reasoning before you open anything.',
  },
  {
    element: '[data-tour="filters"]',
    title: 'Narrow it down',
    description:
      'Supreme Court only? Appeals allowed? Filter by court, outcome, act or section. Counts update live, so you always know how much is left.',
  },
  {
    element: '[data-tour="open-reader"]',
    title: 'Read it in the original',
    description:
      'Opens the real judgment PDF with your passage highlighted on the page — so you can verify it in the source before you cite it.',
  },
  {
    element: '[data-tour="save-group"]',
    title: 'Keep what matters',
    description:
      'Save cases into a matter you can return to. Your matters live under <strong>Groups</strong> in the sidebar, and every search is kept under <strong>History</strong>.',
  },
];

/**
 * localStorage key recording that this browser has seen the tour.
 *
 * Deliberately per-browser, not per-account: it is a UI preference, not user
 * data, and storing it server-side would mean a profiles-table write on every
 * first load. Bump the suffix to re-show the tour to everyone after a redesign.
 */
export const TOUR_SEEN_KEY = 'nirnay.tour.seen.v1';

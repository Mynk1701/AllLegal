// Billing/tier shapes mirrored from the backend (app/api/routes/billing.py).

export type Tier = 'free' | 'pro' | 'internal';

export interface Billing {
  tier: Tier;
  searches_used: number;
  /** null = unlimited (internal or active pro). */
  searches_limit: number | null;
  period_end: string | null;
  status: string | null;
}

export interface SubscribeResponse {
  subscription_id: string;
  key_id: string;
}

/** Fired on `window` after a search (or upgrade) so the NavRail badge re-fetches
 * usage without a full reload. */
export const BILLING_CHANGED_EVENT = 'billing:changed';

export function notifyBillingChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(BILLING_CHANGED_EVENT));
  }
}

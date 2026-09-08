# Billing & Tiers — Setup / Runbook

Operational steps to turn on the payments + tiers feature. Code is already in the repo;
these are the **manual, out-of-repo** steps (Supabase SQL, Razorpay dashboard, env vars).

Do them in this order — **run the SQL before deploying the backend**, so existing testers
are backfilled to `internal` and never hit the paywall.

---

## 1. Supabase — `profiles` table, trigger, backfill

Run in **Supabase → SQL Editor**:

```sql
-- 1a. Table: one billing row per user
create table if not exists public.profiles (
  user_id                  uuid primary key references auth.users(id) on delete cascade,
  tier                     text not null default 'free' check (tier in ('free','pro','internal')),
  provider                 text,
  provider_customer_id     text,
  provider_subscription_id text,
  subscription_status      text,
  current_period_end       timestamptz,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- users may read their own profile; all writes go through the service-role backend
drop policy if exists "own profile read" on public.profiles;
create policy "own profile read" on public.profiles
  for select using (auth.uid() = user_id);

-- 1b. Auto-create a profile on every new signup (signup is client-side and never
--     hits our backend, so a DB trigger is the reliable hook)
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (user_id) values (new.id) on conflict do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- 1c. Backfill everyone who already signed up → internal (they're all our testers today)
insert into public.profiles (user_id, tier)
select id, 'internal' from auth.users
on conflict (user_id) do update set tier = 'internal';
```

Verify: `select tier, count(*) from public.profiles group by tier;` — existing users show as `internal`.

---

## 2. Razorpay dashboard

1. Create an account (test mode works immediately; **live mode needs business KYC**).
2. **Settings → API Keys** → generate keys → note **Key Id** + **Key Secret**.
3. **Subscriptions → Plans → Create Plan**: monthly, INR, your Pro price → note the **Plan Id** (`plan_...`).
4. **Settings → Webhooks → Add Webhook**:
   - URL: `https://alllegal.onrender.com/api/billing/webhook`
   - Secret: choose one → note it (this is `RAZORPAY_WEBHOOK_SECRET`).
   - Active events: `subscription.activated`, `subscription.charged`, `subscription.halted`, `subscription.cancelled`, `subscription.completed`.

---

## 3. Environment variables

**Backend** (local `.env` + Render → Environment):

```
FREE_TIER_SEARCH_LIMIT=15
BILLING_PROVIDER=razorpay
RAZORPAY_KEY_ID=rzp_test_xxx        # rzp_live_... in production
RAZORPAY_KEY_SECRET=xxx
RAZORPAY_WEBHOOK_SECRET=xxx
RAZORPAY_PLAN_ID=plan_xxx
```

**Frontend:** none required — the checkout `key_id` is returned by `/api/billing/subscribe`.

**Install the new dependency** (added to `requirements.txt`):
```
pip install razorpay==1.4.2
```
Render installs it automatically on next deploy.

---

## 4. Comp an internal tester

```
python scripts/set_tier.py tester@example.com internal
```
Also: `... pro` or `... free`. Accepts multiple emails or `--file emails.txt`; `--dry-run` to preview.

---

## 5. Test end-to-end

**Free limit** — temporarily set `FREE_TIER_SEARCH_LIMIT=3` locally:
1. Sign up a fresh user → a `profiles` row appears with `tier='free'`.
2. Do 3 searches (all succeed), 4th → the "used all free searches" banner + a 429 from `/api/search`.
3. NavRail shows the **Free** chip and "0 left".

**Internal** — `python scripts/set_tier.py <you>@… internal` → searches never blocked; NavRail shows **Internal**.

**Upgrade → Pro** (Razorpay **test mode**):
1. Webhook must be publicly reachable — deploy to Render, or tunnel locally
   (`cloudflared tunnel --url http://localhost:8000`) and point the Razorpay webhook at the tunnel.
2. Pricing page → **Upgrade to Pro** → complete Razorpay test payment
   ([test cards](https://razorpay.com/docs/payments/payments/test-card-details/)).
3. Webhook fires → `profiles.tier='pro'`, `current_period_end` set → page polls, then redirects to search. Unlimited; NavRail shows **Pro**.

**Lapse/downgrade** — set `current_period_end` to the past in `profiles`, or send a
`subscription.cancelled` → next search falls back to free-tier counting.

**Regression** — confirm `/api/facets`, history, case-detail, and PDF fetch still work (never metered).

---

## 6. Adding a new tier later

The tier list is data-driven from `app/core/tiers.py`. To add one (e.g. a "team"
plan with 500 searches/month, or a second paid tier):

1. **`app/core/tiers.py`** — add one `TierSpec` entry to `_registry()`. That's the
   only backend code change: quota enforcement, `/billing/me`, `/billing/tiers`, and
   the webhook's plan→tier mapping all read from this registry.
2. **Supabase** — extend the `profiles.tier` CHECK constraint to allow the new key:
   ```sql
   alter table public.profiles drop constraint profiles_tier_check;
   alter table public.profiles add constraint profiles_tier_check
     check (tier in ('free','pro','internal','<new_key>'));
   ```
3. **Razorpay** (only if it's a *paid* tier) — create a plan, put its `plan_...` id in
   the new `TierSpec.plan_id` (via an env var), and set `requires_subscription=True`,
   `purchasable=True`. The webhook resolves the granted tier from the subscription's
   `plan_id`, so no route code changes.

---

## 7. Go live

Flip Razorpay to **live** (after KYC), swap `rzp_test_*` → `rzp_live_*` keys + the live
webhook secret + live plan id in Render env, redeploy. Set `FREE_TIER_SEARCH_LIMIT` back to 15.

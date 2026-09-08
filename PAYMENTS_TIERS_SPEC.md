# Payments & Usage Tiers — Spec

*Status: implemented — this documents the model and the reasoning behind it. For the
operational steps to turn it on (Supabase SQL, Razorpay dashboard, env vars), see
`BILLING_SETUP.md`. Owner: engineering · Last updated: 2026-09-06*

---

## 1. Why we're doing this

We're close to launch. We need two things before we can put this in front of real users:

1. **A way to charge for the product** — meter how much each user searches, and gate it behind a paid plan.
2. **A way for our own testers to use it freely** — so we can test rigorously without hitting a paywall ourselves.

The model we built: a **freemium tier structure with a comped internal tier**, plus a
payment gateway (Razorpay) to collect money.

---

## 2. The model (business)

Three tiers:

| Tier | Who it's for | Searches | Price | How they get it |
|---|---|---|---|---|
| **Internal** | *Our* testers & team | **Unlimited** | Free (comped) | We flip specific emails manually |
| **Free** | Every new signup | **15 / month** (resets monthly) | ₹0 | Default the moment they sign up |
| **Pro** | Paying lawyers | **Unlimited** | **₹500 / month** | They subscribe via Razorpay |

**Rationale**

- **Internal = unlimited, comped** → we test hard without a wall, and our usage never pollutes revenue metrics. This directly answers "put my trial users in a tier where everything is free."
- **Free = the funnel** → 15 searches/month is enough to feel the value, few enough to force a decision. It **resets monthly** so a user who hits the wall comes back next month, tries again, and is nudged to upgrade again — a recurring conversion prompt rather than a one-time hard stop.
- **Pro = flat monthly, unlimited** → simplest thing to explain to a lawyer ("₹500/month, search all you want") and gives us **predictable recurring revenue (MRR)**. If a payment fails/lapses, the account **automatically drops back to Free** — no manual work.

**Only actual searches count.** Browsing results, opening a case, viewing the PDF, filtering
— none of those burn quota. One search = one metered action.

### Numbers to decide (co-founder input needed)
- **Pro price** — ₹? / month. *(Placeholder in the build until we agree.)*
- **Free limit** — 15/month is the starting proposal; trivially changeable (one config value).
- These are **not hard-coded into logic** — we can tune them anytime without a code change.

---

## 3. Why Razorpay (and not Stripe)

- **India-first**: native UPI, cards, and netbanking in INR — what Indian lawyers actually use.
- **Recurring subscriptions** built in.
- **Stripe** is great globally but has more friction for an early Indian company (needs a
  registered entity, weaker UPI support). We're billing Indian customers in INR, so Razorpay wins.
- **Future-proofing**: we're building the payment layer behind a clean interface, so if we
  ever expand internationally we can add Stripe **without rewriting the tier/quota logic**.

> ⚠️ **KYC note:** Razorpay **test mode** works immediately (we can build & demo now). Going
> **live** (taking real money) requires **business KYC** — we'll need the registered entity /
> bank details. Worth starting that paperwork in parallel.

---

## 4. How it works (plain-English flow)

**New user signs up** → automatically gets a **Free** plan (15 searches this month).

**They search** → each search checks: *"What plan are you on, and how many searches have you
used this month?"*
- Internal or active Pro → always allowed.
- Free & under 15 → allowed.
- Free & at 15 → **blocked** with an "Upgrade to Pro" prompt.

**They click Upgrade** → Razorpay's payment window opens → they pay → Razorpay tells our
server → their plan flips to **Pro (unlimited)** instantly.

**A month later, payment renews** automatically. If a renewal **fails**, Razorpay tells our
server and the account **drops back to Free**.

**Our testers** → we run one command to set their email to **Internal** → unlimited forever.

The **sidebar** shows everyone their current plan and, for Free users, "N searches left this
month."

---

## 5. How it works (technical)

Enough detail for an engineer to build/review; skippable for others.

### Key facts about our current system that make this cheap to build
- The backend already **logs every search** to a `search_logs` table (with user + timestamp).
  → That's already a **usage ledger** — we count rows to know usage. No new tracking infra.
- Exactly **one** API endpoint (`GET /api/search`) counts as a "search."
  → Quota is enforced in **one surgical place**, not scattered around.
- The backend is **stateless** (identifies users purely from their login token).
  → We add one small `profiles` table to remember each user's plan.

### Components

**A. Database (Supabase)** — a new `profiles` table, one row per user:
`tier` (free/pro/internal), subscription status, `current_period_end`, Razorpay IDs.
Auto-created for every new signup via a database trigger. Existing users get backfilled to
`internal` (they're all our testers today).

**B. Quota gate (backend)** — a single check attached to the search endpoint: look up the
user's tier, and for Free users count their searches this month; block with `429 Upgrade`
once over the limit. Internal/active-Pro skip the check.

**C. Billing layer (backend)** — a provider-agnostic interface with a Razorpay implementation:
- `POST /api/billing/subscribe` → starts a Razorpay subscription.
- `POST /api/billing/webhook` → Razorpay calls this after payment; we verify it's genuine and
  update the user's plan. **The webhook — not the browser — is the source of truth**, so a
  user who pays and closes the tab still gets upgraded.
- `GET /api/billing/me` → returns the user's plan + usage (powers the sidebar & pricing page).

**D. Frontend (Next.js)**
- A **Pricing/Upgrade page** with plan cards and a "Subscribe" button (opens Razorpay).
- A **plan badge + "searches left"** indicator in the sidebar.
- Graceful **"you're out of searches — upgrade"** message when a Free user hits the wall.

**E. Admin tooling** — a one-line script, `set_tier.py`, to flip a tester's email to
`internal` (or any tier).

### Files (for the eng reviewer)
- New: quota gate, billing routes, billing provider (Razorpay), `set_tier.py` script,
  pricing page, billing types.
- Edited: config, Supabase service (profile + usage-count methods), the search route
  (attach the gate), app entrypoint (register routes), sidebar, search page, env files.
- Supabase (SQL, not in repo): `profiles` table + auto-create trigger + backfill.

---

## 6. Rollout plan (safe order)

1. **DB first**: create the `profiles` table + trigger, backfill all existing users to
   `internal` (so no current tester ever gets walled).
2. **Razorpay dashboard**: create the monthly Pro plan + a webhook; grab the test keys.
3. **Ship backend** (quota gate + billing routes) and **frontend** (pricing page + badge).
4. **Test end-to-end in Razorpay test mode** (no real money): free-limit block, upgrade →
   Pro unlimited, renewal, lapse → auto-downgrade, internal → unlimited.
5. **Go live** once business KYC clears on Razorpay.

---

## 7. Open decisions for this review

| # | Decision | Proposed | Needs |
|---|---|---|---|
| 1 | **Pro price** | ₹___ / month | Co-founder agreement |
| 2 | **Free limit** | 15 / month | Confirm or adjust |
| 3 | **Razorpay account** | Razorpay | Who owns it + start **business KYC** |
| 4 | **Annual plan?** | Not in v1 (monthly only) | Add later? |

---

## 8. Costs / risks

- **Razorpay fee**: ~2% per transaction (standard Indian gateway rate) — factor into pricing.
- **KYC gate**: can build & demo now (test mode); **can't take real money** until KYC clears.
- **Usage-log reliability**: if a search-log write ever fails, a Free user gets a *few extra*
  free searches — harmless (never over-charges), and paid/internal users are unlimited anyway.

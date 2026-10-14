-- Drafting module: matters + generation audit trail (LLD S.3).
--
-- Mirrors the existing `groups`/`group_items`/`annotations` tables: the
-- FastAPI backend talks to these ONLY through the service-role client
-- (app/services/supabase.py), which bypasses RLS, so ownership is enforced
-- in application code (see app/api/routes/drafting.py `_require_matter`),
-- exactly like `_require_group` in app/api/routes/groups.py. RLS is still
-- enabled and deny-all below as defence in depth, in case any other client
-- ever connects with the anon/user key.

create extension if not exists pgcrypto;  -- gen_random_uuid(), already relied on if groups uses it

create table if not exists matters (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,                              -- Supabase auth.users.id (JWT 'sub')
    track_key text not null,                             -- e.g. 'cheque_bounce'
    title text not null,
    facts jsonb not null default '{}'::jsonb,            -- validated against the track's Pydantic model
    facts_schema_version int not null default 1,
    research_group_id uuid references groups(id) on delete set null,  -- Phase 2 link to the research group
    status text not null default 'draft'
        check (status in ('draft', 'in_progress', 'filed', 'closed')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists matters_user_id_updated_at_idx on matters (user_id, updated_at desc);
create index if not exists matters_track_key_idx on matters (track_key);

create table if not exists matter_documents (
    id uuid primary key default gen_random_uuid(),
    matter_id uuid not null references matters(id) on delete cascade,
    user_id uuid not null,
    template_key text not null,                         -- e.g. 'legal_notice'
    template_version text not null,                      -- semver, e.g. '1.0.0'
    facts_hash text not null,                             -- sha256 of the canonical facts JSON at render time
    gaps jsonb not null default '[]'::jsonb,              -- missing required fields at render time
    finalised_at timestamptz,                             -- set once the lawyer attests/adopts the draft
    created_at timestamptz not null default now()
);
create index if not exists matter_documents_matter_id_idx on matter_documents (matter_id, created_at desc);

-- Court-holiday calendar for the complaint-filing deadline's roll-forward
-- rule (app/drafting/deadlines/calendar.py roll_forward_if_closed). Seeded
-- per pilot state/court as the LLD's "pilot jurisdiction decision" is made
-- (LLD S.14.B) — empty by default, which simply means roll-forward never
-- fires until holidays are loaded for that forum.
create table if not exists court_holidays (
    state text not null,
    court_type text not null default 'district',
    holiday_date date not null,
    name text,
    primary key (state, court_type, holiday_date)
);

alter table matters enable row level security;
alter table matter_documents enable row level security;
alter table court_holidays enable row level security;

-- Deny-all for anon/authenticated roles: the service-role key (used by
-- app/services/supabase.py's `admin` client) bypasses RLS entirely, so
-- these policies only matter if a client ever connects with a non-service
-- key — in which case the safe default is "nothing", same posture as
-- `groups`/`annotations` today (which have no RLS policies written either,
-- relying entirely on the service-role + application-level ownership
-- check). No policies are created here on purpose.

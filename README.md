# AllLegal — semantic search over Indian case law

A FastAPI backend and Next.js frontend for searching ~25,000 Supreme Court and
High Court judgments by **meaning**, not keywords. A lawyer types a question and
gets back the passages that actually answer it, grouped by case, with the source
PDF and page highlights.

Search is vector (kNN) retrieval over chunk-level embeddings in OpenSearch.
Filters bound the search; the query ranks within it.

---

## Architecture

```
Next.js (Vercel)  ──▶  FastAPI (Render)  ──┬──▶  OpenSearch (GCE, deploy/gcp)
                                            │      chunk index + kNN + facets
                                            ├──▶  Supabase
                                            │      auth (JWT), case metadata,
                                            │      groups, annotations, search
                                            │      logs, PDF storage
                                            └──▶  Voyage AI
                                                   query embeddings
```

Judgments are ingested by a **separate** repository, `legal-engine` (a submodule
here), which extracts, labels, chunks, embeds and indexes PDFs. This repo only
*reads* that index — it never writes to it.

### How a search works

1. The query is embedded with Voyage `voyage-law-2` (`input_type="query"` — the
   model is asymmetric and the pipeline indexed with `"document"`).
2. OpenSearch runs a `knn` query over `chunk_embedding`, with any active filters
   pushed *inside* the kNN clause as a pre-filter, so filtering never causes a
   recall cliff.
3. `collapse` on `case_id` with `inner_hits` deduplicates chunks into cases
   inside OpenSearch, so `from`/`size` paginate cases rather than chunks.
4. Facets are query-aware and drill-down: each facet excludes its own selection,
   and counts are distinct *cases* via a `cardinality` sub-aggregation.
5. Suppression re-runs the query unfiltered to surface strong matches the filters
   are hiding, naming which filter excludes them.

Details and the reasoning behind each choice are in the module docstrings of
`app/services/opensearch_service.py` and `app/api/routes/search.py`.

---

## Tech stack

| Component | Technology |
|---|---|
| API | FastAPI + Pydantic (typed request/response models) |
| Search | OpenSearch 2.19.5, Lucene HNSW k-NN, 1024-dim vectors |
| Embeddings | Voyage AI `voyage-law-2` |
| Auth | Supabase JWT, verified against the project JWKS (ES256) |
| Data | Supabase Postgres + Supabase Storage (case PDFs) |
| Billing | Razorpay subscriptions |
| Frontend | Next.js (App Router) + Tailwind |

---

## Repository layout

```
app/
  api/routes/     search, cases, groups, billing endpoints
  core/           config (env-driven settings), security (JWT), quota, tiers
  services/       opensearch, embeddings, supabase, billing providers, case_index
  schemas/        Pydantic request/response models
deploy/gcp/       production OpenSearch: compose, index mapping, migration, backups
deploy/oracle/    the predecessor host — kept for its two incident write-ups
frontend/         Next.js app
scripts/          one-off operational scripts (tier changes, PDF upload, user cleanup)
vendor/           statute_index + annotatedCentralActs, vendored so deploys that
                  cannot clone the private legal-engine submodule still work
legal-engine/     git submodule — the ingestion pipeline (separate repo)
```

---

## Quick start

```bash
./setup.sh            # or setup.bat on Windows: venv + pip + npm install
cp .env.example .env  # then fill in Supabase + Voyage credentials
docker compose up -d  # local OpenSearch on :9200 (dev only, no auth)
python main.py        # API on :8000
cd frontend && npm run dev
```

`.env.example` lists every key the app reads. Anything with a working default
lives in `app/core/config.py` instead.

A fresh local OpenSearch starts **empty** — search will return nothing until an
index exists. Create it with the mapping in `deploy/gcp/case_chunks_v2.json` and
load data via the `legal-engine` pipeline.

---

## API

All endpoints are under `/api` and require a Supabase JWT bearer token, except
`/api/billing/webhook` (verified by Razorpay HMAC signature instead).

| Endpoint | Purpose |
|---|---|
| `GET /search` | Semantic + filtered search → case-grouped results, facets, suppressed matches. **Metered** against the caller's tier quota. |
| `GET /facets` | Query-aware drill-down filter options (first paint / standalone) |
| `GET /search/history` | The caller's past search definitions, de-duplicated |
| `GET /search/health` | OpenSearch connectivity |
| `GET /cases/{case_id}` | Full case detail: all chunks in order, metadata, PDF URL |
| `GET/POST/DELETE /groups...` | Case groups, their items, and annotations |
| `GET /billing/me` | Current tier, usage, and limit |
| `GET /billing/tiers` | Purchasable tiers |
| `POST /billing/subscribe` | Start a Razorpay subscription |
| `POST /billing/webhook` | Razorpay events — the source of truth for tier changes |

`GET /search` is the only metered endpoint: `app/core/quota.py` counts
`search_logs` rows since the start of the calendar month and compares against the
tier's limit.

---

## Tiers

Defined in one place — `app/core/tiers.py`. Adding a tier is a single registry
entry (plus a Supabase CHECK-constraint value and, if paid, a Razorpay plan).

| Tier | Limit | How you get it |
|---|---|---|
| `free` | 15 searches / calendar month | default for every new account |
| `pro` | unlimited | active Razorpay subscription (₹500/month) |
| `internal` | unlimited | set manually (`scripts/set_tier.py`) |

See `BILLING_SETUP.md` for the Supabase SQL, Razorpay dashboard setup, and the
end-to-end test plan.

---

## Deployment

| Piece | Where |
|---|---|
| Backend | Render (Oregon) |
| Frontend | Vercel |
| OpenSearch | Self-hosted single node on GCE `us-west1` — see `deploy/gcp/README.md` |
| Postgres, auth, PDF storage | Supabase (hosted) |

`deploy/gcp/README.md` carries the operational runbook: sizing rationale,
security posture, backup/restore, and the rebuild path.

---

## Known issues

`SEARCH_AND_FILTERS_BACKLOG.md` tracks open search/filter gaps.

---

## 🖊️ Drafting Module (Phase 1 — Cheque Bounce)

`app/drafting/` generates the fixed-format filings for a litigation track —
starting with cheque bounce (S.138 NI Act) — from facts the lawyer enters
once. Full design: [`plans/read-alllegal-drafting-module-track-spec-keen-ladybug.md`](plans/read-alllegal-drafting-module-track-spec-keen-ladybug.md).

**One-time setup**

```bash
pip install -r requirements.txt     # adds PyYAML, docxtpl, python-docx
psql < supabase/migrations/0001_drafting.sql   # or run it via the Supabase SQL editor
python3 scripts/build_drafting_templates.py    # generates app/drafting/tracks/cheque_bounce/templates/*.docx
```

Re-run `build_drafting_templates.py` only when a template's STRUCTURE
changes (a new field, a new conditional block) — wording changes are made
by opening the generated `.docx` directly in Word; the Jinja tags are plain
text and safe to leave alone.

**Run the unit tests** (deadline engine, formatters, calendar — pure
Python, no DB/FastAPI needed):

```bash
pytest tests/drafting/
```

**API** (mounted under `/api`, same auth as `/api/groups`):

| Endpoint | Purpose |
|---|---|
| `GET /api/drafting/tracks` | Enabled tracks |
| `GET /api/drafting/tracks/{key}` | One track's stages/fields/documents |
| `POST /api/drafting/matters` | Create a matter for a track |
| `GET /api/drafting/matters` / `/{id}` | List / fetch a matter |
| `PATCH /api/drafting/matters/{id}/facts` | Save one section of facts (autosave) |
| `GET /api/drafting/matters/{id}/deadlines` | Computed S.138 deadlines |
| `GET /api/drafting/matters/{id}/readiness` | Per-document readiness (missing facts / blocking issues) |
| `POST /api/drafting/matters/{id}/documents/{template_key}` | Generate a `.docx` (e.g. `legal_notice`) |
| `POST /api/drafting/matters/{id}/documents/{document_id}/finalise` | Record the lawyer's sign-off |

Only `legal_notice` has a built template today (the Phase-1 vertical
slice); the other five cheque-bounce documents are configured in
`app/drafting/tracks/cheque_bounce/track.yaml` but still need their
`.docx` templates built per the LLD's M4 step.


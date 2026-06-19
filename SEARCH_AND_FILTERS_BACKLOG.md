# Search & Filters — Known Issues Backlog

Found while reviewing the search/filter implementation (`app/api/routes/search.py`,
`app/services/opensearch_service.py`, `frontend/app/page.tsx`) after the first real
ingest (250 cases, ~8,931 chunks). Mirrors the style of `legal-engine/misc/future_changes.md`
but scoped to the FastAPI app + frontend layer instead of the ingestion pipeline.

Status legend: ✅ fixed · 🔴 open, not started · 🟡 open, stopgap applied

> **Note (post-merge):** a round of these fixes was applied, then lost when a `git pull`
> brought in `parth/pdf-reader` (merged as `7e69873`) and reverted several files to their
> pre-fix state. All of it has been re-applied on top of the merged code as of this writing.
> The merge also brought its own independent fix (search-history replay, see below) and a
> StatuteIndex path correction in `search.py` — both kept, not reverted.

---


---

## 🔴 `case_type` is filterable in the API/UI but never populated at ingest

`stage_05_index.py` has its own TODO: `"case_type": meta.get("case_type")` is never
actually extracted anywhere in the pipeline, so the field is always absent from indexed
docs. The frontend's facet-driven checkboxes (fixed to hide empty sections) correctly show
nothing for Case Type, but the underlying gap — no case-type extraction — is still open if
this is wanted as a real filter dimension later.

**Where:** `legal-engine/pipeline_runner/stage_05_index.py` (`case_level_fields`).

---

## 🔴 Facet counts are approximate under an active semantic query

`opensearch_service.facets()` aggregates over a `knn` base query capped at
`FACET_POOL_K` (500 nearest chunks) when a query is present — counts only reflect that
pool, not the full filtered set. Reasonable performance tradeoff, but nothing in the UI
indicates these are estimates, and it gets less accurate as the corpus grows past 500
chunks per typical query. (With no query — `match_all` — facet counts ARE exact; this only
applies when semantic search is active.)

**Where:** `app/services/opensearch_service.py` (`facets()`), `app/core/config.py` (`FACET_POOL_K`).

---

## 🔴 `bench_strength` is fully wired end-to-end but has no UI control

Real, populated, filterable/facetable field (API param, OpenSearch field, facet response)
— just nothing in `page.tsx` renders a checkbox/input for it. Not a bug, just an unused
capability if/when it's wanted.

---

## 🔴 Year-range inputs: server-side validation still swallowed silently

Mitigated client-side (inputs are now `type="number"`), but if a non-numeric value still
reaches the API somehow, FastAPI's `int` query coercion returns a 422 that the frontend's
`catch` swallows silently — user sees nothing happen, no error shown. Low priority given the
client-side mitigation, listed for completeness.

**Where:** `frontend/app/page.tsx` (`runSearch`).

---


---

## 🔴 Malformed section facet values with no act name (`" s.3"`, `" s.7"`)

**Found via live index check (2026-06-19):** aggregating `sections_cited` on the real
`case_chunks` index turned up two values that are just a section number with a leading space
and no act prefix — `" s.3"` (97 docs) and `" s.7"` (86 docs). Every other section value
follows `"<act> s.<n>"` (e.g. `"NI s.138"`), so these two break that invariant — and would
also break the new Acts→Sections cascade in `page.tsx`, since `value.startswith("<act> s.")`
can never match an empty act prefix (they'd just silently never show up under any act).

**Likely cause:** `StatuteIndex.lookup()` returning a `canonical` with an empty `act` half of
the `" s."`-partition for some specific raw citation text — needs tracing through which
`statute_tags` extraction produced this (ingest-side, Parth's pipeline run), not something
fixable from the AllLegal app layer alone.

**Where:** `legal-engine/src/scripts/statute_index.py` (`lookup()`), `legal-engine/LangExtract/chunk_info_extractor.py` (`post_process_field` for `statute_tags`).

---

## 🔴 Other previously-noted gaps (carried over, still open)

- OpenSearch mapping declares `acts_cited_raw` / `sections_cited_raw` / `cases_cited_raw`
  but `stage_05_index.py` never populates them.
- Lower-court verdicts are dropped entirely from both OpenSearch and Supabase by design
  (avoids contradictory rollups) — open product decision on whether that's wanted as a
  separate filterable field.
- No replicas (`number_of_replicas: 0`) and OpenSearch security plugin disabled — explicitly
  dev-only, needs hardening before any networked deployment.
- Stage 2 (InLegalBERT) classification is unbatched (one block at a time) — pipeline's own
  TODO, biggest compute lever left on the table (10-30x).

---

## Already fixed (for reference — don't re-investigate)

- ✅ `annotatedCentralActs/` dataset — resolved (2026-06-19). Parth provided
  `annotatedCentralActs.zip` (858 act JSON files), `case_identity_table.zip`, and
  `reverse_lookup.zip`. Extracted to `AllLegal\legal-engine\` — **not** the sibling location
  (`C:\Users\sarit\project\annotatedCentralActs\`) suggested earlier in this doc, which was
  wrong; corrected by tracing `statute_index.py`'s own `DATASET_DIR` computation
  (`Path(__file__).parent.parent.parent` = the `legal-engine` dir itself) and cross-checking
  against `LangExtract/output/` paths in Parth's instructions. Also found and fixed a
  separate, pre-existing bug while verifying this: `STATUTE_INDEX_PATH` in `search.py` used
  `parents[4]`, resolving to `C:\Users\sarit\project` (one level too high — the parent of
  `AllLegal`, not `legal-engine`), so `from statute_index import StatuteIndex` had been
  silently failing (`statute_index = None`) in this environment this entire session,
  independent of whether the dataset existed. Fixed to `parents[3] / "legal-engine" / "src" /
  "scripts"`. Verified end-to-end: `StatuteIndex` now loads 149,322 entries (up from 21,844
  hardcoded-only), and `_act_label()` correctly resolves real names, e.g. `NI` → `"THE
  NEGOTIABLE INSTRUMENTS ACT, 1881 (NI Act)"`. `case_identity_table.json`/`reverse_lookup.json`
  are an unrelated ingest-side dependency (`legal-engine/LangExtract/case_citation_lookup.py`'s
  `CitationResolver`, used for precedent-citation resolution at extraction time) — confirmed
  zero references in `app/`, so they don't affect the running API, only future `legal-engine`
  ingest runs. Worth noting: `CitationResolver`'s constructor has no try/except around
  reading these files (unlike `StatuteIndex`), so their absence would hard-crash ingest on any
  precedent-citation chunk — likely why Parth needed to send them now.
- ✅ Chunk-density undercount, properly fixed (2026-06-19) — root cause: search paginated by
  CHUNKS fetched (`fetch_size`, via tuned constant `CHUNK_FETCH_FACTOR`) and grouped into
  cases client-side (`_group_by_case`), so a fixed chunk budget translated unpredictably into
  case count whenever chunks-per-case varied a lot (confirmed live: 1-107 chunks/case for the
  same court filter). Reproduced exactly: `court=Supreme Court of India` landed on precisely
  14 cases because `fetch_size`'s chunk budget happened to cross a year-boundary that contains
  exactly 2 cases/year × 7 years. Fixed by replacing the whole estimate with OpenSearch
  `collapse: {field: "case_id"}` + `inner_hits` in `opensearch_service.search()` — OpenSearch
  now dedups chunks onto cases itself, `from`/`size` paginate the deduplicated set directly
  (exact, no estimate). `_group_by_case` replaced by `_hits_to_case_groups` (a reshape, not a
  grouping — OpenSearch already grouped). Verified against the live cluster (OpenSearch
  2.19.5, Lucene k-NN engine): non-overlapping pages, `knn`+`collapse` combination works
  correctly (the known collapse gap is for the unrelated neural-search `hybrid` query type,
  not the plain `knn` query used here).

  First pass sized the kNN candidate pool (`k`) with a `page*limit*multiplier` heuristic —
  same family of guess as the bug it replaced, just better-tuned, and empirically still ran
  out of margin by page 3-4 (measured: only 42 distinct cases reachable within k=400, but
  page 4 needs 40 — a 2-case margin). Replaced that with the actual permanent fix: `k` is now
  sized to the EXACT count of chunks matching the active filters, via a cheap `_count` call
  (~20-50ms) in `opensearch_service.search()`, capped only by `KNN_K_CEILING` (5000) as a
  performance safety net for a deliberately huge unfiltered query. This makes `total_cases`
  exact in BOTH modes (not just filter-only), and confirmed zero shortfall through every page
  of the full 50-case test corpus, including the literal last page. `KNN_K_PER_CASE_MULTIPLIER`
  removed; `KNN_K` repurposed to mean only `suppressed_matches()`'s fixed scan depth, unrelated
  to `/search` pagination now.
- ✅ Dead `COURT_MAP` and court/verdict/case_type string-remapping hacks removed from
  `_normalize_filters` now that the frontend sources filter values from `/api/facets`.
- ✅ `acts_cited` normalization parity added (was sections_cited-only before).
- ✅ Frontend filter checkboxes (Jurisdiction/Case Type/Outcome) now driven by `/api/facets`
  instead of hardcoded option arrays; empty facets (e.g. Case Type) hide their section.
- ✅ Year-range inputs show real corpus min/max as placeholders, and are `type="number"`.
- ✅ Trailing-comma empty filter values from Acts/Sections free text — already fixed
  independently in the `parth/pdf-reader` merge (`collectFilters()` filters falsy entries).
- ✅ Search-history replay restoring filters, not just query text — already fixed
  independently in the `parth/pdf-reader` merge (`SearchFilters`/`collectFilters`/`runSearch`/
  `applyHistory`); simplified further here since checkboxes now carry canonical values
  directly (no more reverse-mapping needed in `applyHistory`).
- ✅ `ef_search` kNN param removed from `opensearch_service.search()` (no-op on OpenSearch's
  Lucene HNSW engine, which uses `k` instead).
- ✅ Dead `app/services/pdf.py` (PyPDF2) removed, `PyPDF2` dropped from `requirements.txt`.
- ✅ `verdict` schema type mismatch — `CaseResult.verdict`/`CaseDetail.verdict`
  (`app/schemas/schemas.py`) changed from `Optional[str]` to `List[str]`, coerced via a
  shared `_normalize_verdict()` + `field_validator(mode="before")` so list/JSON-string/bare-string
  source shapes all land as `list[str]`. Frontend `verdict` typed as `string[]` in both
  `frontend/types/legal.ts` and `frontend/lib/reader/types.ts`; defensive `parseVerdict()`
  workarounds removed from `page.tsx` and the independently-duplicated copy in
  `components/reader/MetadataPanel.tsx` (same bug existed there too).
- ✅ Dead Supabase methods removed: `insert_case`, `get_case` (distinct from `get_case_by_id`),
  `search_cases` — referenced a schema (`title`, UUID `id`) that didn't match the real `cases`
  table, and had zero callers anywhere in the app or frontend.
- ✅ `logger` referenced before definition in `search.py`'s `StatuteIndex` import fallback
  (no longer an issue post-merge — the upstream version already defines `logger` first).
- ✅ Dead Meilisearch service and unused SQLAlchemy (search-history migrated to `supabase-py`,
  `app/db/` removed entirely).
- ✅ Acts/Sections filter converted from free text to a facet-driven, cascading picker:
  Sections only renders once an Act is selected, scoped to that act via an exact
  `value.startswith("<act> s.")` prefix match (`acts_cited`/`sections_cited` are written
  from the same `act` variable at extraction time — see `chunk_info_extractor.py`/
  `statute_index.py`, so this is exact, not heuristic). `selectedSections` auto-prunes if its
  parent act is unchecked. `FacetValue.label` (new, `app/schemas/schemas.py`) carries a
  lawyer-friendly display name for acts (via `StatuteIndex.get_act_inventory_entry`) and a
  "(formerly IPC/CrPC N)" suffix for sections with a legacy BNS/BNSS mapping, attached
  server-side in `search.py`'s `_attach_facet_labels()`. Both Acts and Sections groups get a
  type-ahead filter box once a group passes 8 options. See the `annotatedCentralActs/` gap
  above for the one open limitation (label quality outside the 5 hardcoded acts).

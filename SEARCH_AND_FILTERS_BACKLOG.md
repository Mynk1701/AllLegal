# Search & Filters — open issues

Scoped to the FastAPI app + frontend. Ingestion-pipeline issues belong in
`legal-engine`, not here.

All figures below were re-verified against the live index on 2026-09-06
(465,398 chunks / 25,404 cases). Entries that turned out to be fixed have been
removed rather than archived — `git log` is the history.

---

## 🔴 `total_cases` is a function of `k`, not of the corpus

`opensearch_service.search()` computes the result total with a
`cardinality(case_id)` aggregation nested under the `knn` query — so the
aggregation only ever sees the `k` retrieved chunks. Measured:

| `k` | `hits.total` | reported distinct cases |
|---|---|---|
| 500 | 500 | 388 |
| 1500 | 1500 | 1058 |
| 5000 | 5000 | 3066 |

`hits.total` equals `k` exactly. The count shown to users is therefore pinned
near 1058 regardless of how large the corpus grows.

Related: `KNN_K_CEILING` was sized on the assumption of ~3 chunks/case, but 3 is
`MAX_CHUNKS_PER_CASE` (a display cap). Real corpus fanout is **18.3 chunks/case**
(max 1,445), so a single large case can consume most of a `k=1500` pool.

**Fix:** take the total from a filter-only `cardinality` aggregation (measured at
167 ms over the full corpus, independent of `k`) and derive `k` from page depth ×
mean fanout, with a shortfall retry. Full design in §10 of the GCP migration plan.

**Where:** `app/services/opensearch_service.py` (`search()`), `app/core/config.py`
(`KNN_K_CEILING`).

---

## 🔴 Facet counts are a small sample under an active semantic query

`facets()` aggregates over a `knn` pool capped at `FACET_POOL_K` (500 chunks).
At 18.3 chunks/case that is roughly **380 of 25,404 cases** — close to a random
sample, and nothing in the UI marks the counts as estimates. With no query
(`match_all`) the counts *are* exact; this only applies to semantic search.

Same root cause as the entry above, and the same fix applies: scope facet
aggregations to the filter-only query, or keep them query-aware and label them
approximate. Query-aware facets are a deliberate design choice, so this is a
product call, not purely a bug.

**Where:** `app/services/opensearch_service.py` (`facets()`), `app/core/config.py`
(`FACET_POOL_K`).

---

## 🔴 Malformed `sections_cited` values with no act prefix

Every well-formed section value follows `"<act> s.<n>"` (e.g. `"NI s.138"`). A
large set of values are instead a bare section number with a leading space and no
act — they break that invariant, and the Acts→Sections cascade in `FilterBar.tsx`
matches on `value.startswith("<act> s.")`, so these can never appear under any
act and are silently unreachable in the UI.

**This is much larger than previously recorded.** The earlier note listed two
values at ~90 docs each; the live index has at least ten in the top 300 alone:

| value | docs | | value | docs |
|---|---|---|---|---|
| `" s.3"` | 27,914 | | `" s.9"` | 14,821 |
| `" s.2"` | 24,083 | | `" s.7"` | 13,452 |
| `" s.4"` | 22,310 | | `" s.8"` | 13,450 |
| `" s.5"` | 19,950 | | `" s.11"` | 11,575 |
| `" s.6"` | 17,121 | | `" s.13"` | 10,826 |

That is >175,000 chunk-level citations unreachable through the section filter.

**Cause:** `StatuteIndex.lookup()` returning a `canonical` whose act half of the
`" s."` partition is empty. Ingest-side — not fixable from the app layer.

**Where:** `legal-engine/src/scripts/statute_index.py` (`lookup()`),
`legal-engine/LangExtract/chunk_info_extractor.py` (`post_process_field`).

---

## 🔴 `case_type` is a filter that can never match

`case_type` is an API query parameter, an OpenSearch mapping field, and a facet —
but it is populated on **0 of 465,398 chunks**. The pipeline never extracts it
(`stage_05_index.py` carries its own TODO). `FilterBar.tsx:259` correctly hides
the section when the facet comes back empty, so there is no visible breakage; the
gap is that the dimension does not exist at all.

Either extract it in the pipeline or drop it from the mapping, filter params and
schema — carrying a dead filter through three layers is the worst of both.

**Where:** `legal-engine/pipeline_runner/stage_05_index.py`;
`app/api/routes/search.py`, `app/services/opensearch_service.py` (`TERM_FACETS`).

---

## 🔴 `*_raw` mapping fields are never populated

`acts_cited_raw`, `sections_cited_raw` and `cases_cited_raw` are declared in the
index mapping and populated on **0 documents** each. They cost mapping surface
and confuse anyone reading the schema. Drop them from the mapping, or populate
them — they were presumably intended to preserve pre-normalization citation text,
which would be genuinely useful for debugging the entry above.

**Where:** `deploy/gcp/case_chunks_v2.json`,
`legal-engine/docker/opensearch/index_mappings/case_chunks.json`.

---

## 🔴 Lower-court verdicts are dropped entirely

By design, to avoid contradictory rollups — but that means a case's lower-court
outcome is unavailable anywhere. Open product decision on whether it should
return as a separate filterable field.

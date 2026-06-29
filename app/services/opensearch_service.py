"""
OpenSearch service for the chunk-level `case_chunks` index.

Search model (see design):
  - Hard filters always BOUND the search; the semantic query RANKS within it.
  - Mode A (query present): filtered-ANN — filters pushed inside the kNN clause
    (pre-filter, never post-filter, so no recall cliff). Lucene engine adaptively
    runs exact search when the filtered set is small.
  - Mode B (no query): pure bool.filter, sorted by date_decided desc.
  - Facets: query-aware + drill-down (each facet excludes its own selection),
    counts are DISTINCT CASES via a cardinality(case_id) sub-agg.
  - Suppression: re-run the query UNfiltered to surface strong matches the hard
    filters are hiding, naming which filter excludes them.
"""
import logging

from opensearchpy import OpenSearch

from app.core.config import settings

logger = logging.getLogger(__name__)

# Case-level metadata is denormalised onto every chunk doc — enough for display
# fallback + local suppression checks without a Supabase round trip.
SOURCE_FIELDS = [
    "case_id", "chunk_id", "chunk_type", "chunk_text", "chunk_sequence",
    "court", "case_type", "verdict", "citation", "parties",
    "acts_cited", "sections_cited", "date_decided", "bench_strength",
]

# Keyword/numeric fields exposed as hard filters + facets.
TERM_FACETS = ["court", "case_type", "verdict", "acts_cited", "sections_cited", "bench_strength"]


class OpenSearchService:
    def __init__(self):
        auth = (settings.OPENSEARCH_USER, settings.OPENSEARCH_PASSWORD) if settings.OPENSEARCH_USER else None
        self.client = OpenSearch(
            hosts=[{"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}],
            http_auth=auth,
            use_ssl=settings.OPENSEARCH_USE_SSL,
            verify_certs=settings.OPENSEARCH_VERIFY_CERTS,
            ssl_show_warn=False,
            # search() + facets() + suppressed_matches() now issue concurrent
            # requests (see search.py thread pools); size the connection pool to
            # match so they reuse sockets instead of opening throwaway ones
            # ("Connection pool is full, discarding connection" with the default 1).
            # NB: opensearch-py's kwarg is `pool_maxsize`, not urllib3's `maxsize`.
            pool_maxsize=8,
        )
        self.index = settings.OPENSEARCH_INDEX

    def health_check(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception as e:
            logger.error(f" OpenSearch ping failed: {e}")
            return False

    # ---------------------------------------------------------------- filters
    def _filter_clauses(self, filters: dict, exclude: str | None = None) -> list:
        """Build bool.filter clauses from the selected hard filters.
        `exclude` omits one facet's own selection (drill-down)."""
        clauses: list = []
        for key in TERM_FACETS:
            if key == exclude:
                continue
            vals = filters.get(key)
            if not vals:
                continue
            if not isinstance(vals, list):
                vals = [vals]
            clauses.append({"terms": {key: vals}})
        if exclude != "year":
            yf, yt = filters.get("year_from"), filters.get("year_to")
            if yf or yt:
                rng = {}
                if yf:
                    rng["gte"] = f"{int(yf)}-01-01"
                if yt:
                    rng["lte"] = f"{int(yt)}-12-31"
                clauses.append({"range": {"date_decided": rng}})
        return clauses

    # ----------------------------------------------------------------- search
    def search(self, *, query_vector, filters: dict, page: int, limit: int) -> tuple[list, int]:
        """One hit per distinct case_id (top MAX_CHUNKS_PER_CASE chunks via
        `collapse`+`inner_hits`), paginated at the case level, plus the
        distinct-case total for this query (`cardinality` agg in the same
        request — no extra round trip). Exact in both modes: filter-only mode
        scans every matching doc; semantic-query mode sizes its kNN candidate
        pool (k) to the exact matching-chunk count via a cheap `_count` call,
        so it's exact too as long as that count is under KNN_K_CEILING.

        `collapse` does the chunk->case dedup inside OpenSearch itself, so
        `from`/`size` here mean cases, not chunks — this replaces the old
        chunk-budget estimate (CHUNK_FETCH_FACTOR), which broke down because
        chunks-per-case varies wildly (1-107x in the real corpus) and a fixed
        multiplier can't track that. Verified against this exact OpenSearch
        version (2.19.5, Lucene k-NN engine): a native `knn` query clause
        combined with `collapse`+`inner_hits` works correctly — the known
        collapse gap (github.com/opensearch-project/neural-search#665) is for
        the neural-search plugin's separate `hybrid` compound query type, not
        the plain `knn` query used here.
        """
        clauses = self._filter_clauses(filters)
        collapse = {
            "field": "case_id",
            "inner_hits": {
                "name": "top_chunks",
                "size": settings.MAX_CHUNKS_PER_CASE,
                "sort": [{"_score": "desc"}] if query_vector is not None else [{"chunk_sequence": "asc"}],
            },
        }
        aggs = {"distinct_cases": {"cardinality": {"field": "case_id"}}}

        if query_vector is not None:
            # k = candidate pool of NEIGHBOUR CHUNKS, pre-collapse. Sized to the
            # EXACT number of chunks that match the active filters (a cheap
            # _count call, ~20-50ms) rather than guessed — that makes k cover
            # every real candidate whenever the filtered set fits under the
            # ceiling, so collapse can surface every distinct case, not just a
            # margin estimated from a multiplier. Only degrades to an
            # approximate top-k once the filtered set exceeds KNN_K_CEILING
            # (a deliberately huge, unfiltered, full-corpus query) — verified
            # empirically that this exact-count approach gives correct,
            # non-shortfalling pagination through every page, where a
            # page*limit-scaled multiplier ran out of margin by page 3-4.
            count_query = {"bool": {"filter": clauses}} if clauses else {"match_all": {}}
            matching_chunks = self.client.count(index=self.index, body={"query": count_query})["count"]
            k = min(matching_chunks, settings.KNN_K_CEILING)
            # No method_parameters.ef_search here: OpenSearch's Lucene HNSW engine
            # ignores it and dynamically uses k instead, so setting it is a no-op.
            knn = {"chunk_embedding": {"vector": query_vector, "k": k}}
            if clauses:
                knn["chunk_embedding"]["filter"] = {"bool": {"filter": clauses}}
            body = {
                "from": (page - 1) * limit,
                "size": limit,
                "_source": SOURCE_FIELDS,
                "query": {"knn": knn},
                "collapse": collapse,
                "aggs": aggs,
            }
        else:
            query = {"bool": {"filter": clauses}} if clauses else {"match_all": {}}
            body = {
                "from": (page - 1) * limit,
                "size": limit,
                "_source": SOURCE_FIELDS,
                "query": query,
                "sort": [{"date_decided": "desc"}],
                "collapse": collapse,
                "aggs": aggs,
            }
        resp = self.client.search(index=self.index, body=body)
        total = resp.get("aggregations", {}).get("distinct_cases", {}).get("value", 0)
        return resp["hits"]["hits"], total

    def get_case_chunks(self, case_id: str) -> list:
        """All chunks for one case, in document order — powers the case-detail view."""
        body = {
            "size": 2000,
            "_source": SOURCE_FIELDS,
            "query": {"term": {"case_id": case_id}},
            "sort": [{"chunk_sequence": "asc"}],
        }
        return self.client.search(index=self.index, body=body)["hits"]["hits"]

    # ----------------------------------------------------------------- facets
    def facets(self, *, query_vector, filters: dict) -> dict:
        """Query-aware, drill-down facets with distinct-case counts."""
        base = (
            {"knn": {"chunk_embedding": {"vector": query_vector, "k": settings.FACET_POOL_K}}}
            if query_vector is not None
            else {"match_all": {}}
        )
        aggs: dict = {}
        for field in TERM_FACETS:
            aggs[field] = {
                "filter": {"bool": {"filter": self._filter_clauses(filters, exclude=field)}},
                "aggs": {
                    "vals": {
                        "terms": {"field": field, "size": settings.FACET_TERMS_SIZE},
                        "aggs": {"cases": {"cardinality": {"field": "case_id"}}},
                    }
                },
            }
        aggs["year_bounds"] = {
            "filter": {"bool": {"filter": self._filter_clauses(filters, exclude="year")}},
            "aggs": {
                "min_year": {"min": {"field": "date_decided", "format": "yyyy"}},
                "max_year": {"max": {"field": "date_decided", "format": "yyyy"}},
            },
        }
        resp = self.client.search(index=self.index, body={"size": 0, "query": base, "aggs": aggs})
        return self._format_facets(resp.get("aggregations", {}))

    @staticmethod
    def _format_facets(aggs: dict) -> dict:
        out: dict = {}
        for field in TERM_FACETS:
            buckets = aggs.get(field, {}).get("vals", {}).get("buckets", [])
            # count = distinct cases (cardinality), not chunk doc_count
            out[field] = [{"value": b["key"], "count": b["cases"]["value"]} for b in buckets]
        yb = aggs.get("year_bounds", {})

        def _year(agg_key):
            s = yb.get(agg_key, {}).get("value_as_string")
            return int(s) if s else None

        out["year_range"] = {"min": _year("min_year"), "max": _year("max_year")}
        return out

    # ------------------------------------------------------------ suppression
    def suppressed_matches(self, *, query_vector, filters: dict, result_case_ids: set, top_n: int = 3) -> list:
        """Strong matches the hard filters are hiding. Only meaningful when a query
        AND at least one filter are present."""
        if query_vector is None or not self._filter_clauses(filters):
            return []
        body = {
            "size": settings.KNN_K,
            "_source": SOURCE_FIELDS,
            "query": {"knn": {"chunk_embedding": {"vector": query_vector, "k": settings.KNN_K}}},
        }
        hits = self.client.search(index=self.index, body=body)["hits"]["hits"]
        suppressed: list = []
        seen: set = set()
        for h in hits:
            src = h["_source"]
            cid = src.get("case_id")
            if cid in result_case_ids or cid in seen:
                continue
            failing = self._failing_filters(src, filters)
            if failing:  # excluded specifically because it fails a filter
                suppressed.append({
                    "case_id": cid,
                    "case_name": src.get("parties") or "",
                    "score": h.get("_score"),
                    "failing_filters": failing,
                })
                seen.add(cid)
                if len(suppressed) >= top_n:
                    break
        return suppressed

    @staticmethod
    def _failing_filters(src: dict, filters: dict) -> list:
        """Which active filters this case's metadata fails."""
        failing = []
        for key in TERM_FACETS:
            vals = filters.get(key)
            if not vals:
                continue
            if not isinstance(vals, list):
                vals = [vals]
            field_val = src.get(key)
            present = field_val if isinstance(field_val, list) else [field_val]
            if not any(v in present for v in vals):
                failing.append({"field": key, "value": vals})
        yf, yt = filters.get("year_from"), filters.get("year_to")
        dd = src.get("date_decided")
        if dd and (yf or yt):
            yr = int(str(dd)[:4])
            if (yf and yr < int(yf)) or (yt and yr > int(yt)):
                failing.append({"field": "year", "value": {"from": yf, "to": yt}})
        return failing


opensearch_service = OpenSearchService()

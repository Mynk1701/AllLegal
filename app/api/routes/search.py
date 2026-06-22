"""
Search API routes.

  GET /api/search          semantic (kNN) + hard filters -> case-grouped results + facets
  GET /api/facets          query-aware, drill-down filter options (first paint / standalone)
  GET /api/search/history  the current user's past search definitions (de-duplicated)
  GET /api/search/health   OpenSearch connectivity

Design: filters always BOUND the search, the query RANKS within it. Search is a
pure function of {query, filters} — there is no "filter first vs query first".
"""
import json
import logging
import time
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.schemas.schemas import (
    CaseResult,
    Facets,
    HistoryItem,
    MatchedChunk,
    SearchResponse,
    SuppressedCase,
)
from app.services.embeddings import embedding_service
from app.services.opensearch_service import opensearch_service
from app.services.supabase import supabase_service

import sys
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()

# Connect to the data pipeline's StatuteIndex (statute-citation normalization).
# Primary source: the `legal-engine` git submodule (AllLegal/legal-engine, see
# .gitmodules) — kept in sync with the upstream pipeline for local dev. That
# submodule is private and owned by a different GitHub account, so deploy
# platforms (Render, Vercel) can't clone it — only AllLegal's own repo gets
# cloned there. Fallback: vendor/statute_index/ is a plain, tracked copy of the
# same statute_index.py + annotatedCentralActs/ dataset, committed directly
# into this repo, so the feature still works in any environment that doesn't
# have submodule access.
# parents[3] = AllLegal (search.py: routes→api→app→AllLegal).
_ALLLEGAL_ROOT = Path(__file__).resolve().parents[3]
_SUBMODULE_PATH = _ALLLEGAL_ROOT / "legal-engine" / "src" / "scripts"
_VENDORED_PATH = _ALLLEGAL_ROOT / "vendor" / "statute_index"
STATUTE_INDEX_PATH = (
    _SUBMODULE_PATH if (_SUBMODULE_PATH / "statute_index.py").exists() else _VENDORED_PATH
)
if str(STATUTE_INDEX_PATH) not in sys.path:
    sys.path.insert(0, str(STATUTE_INDEX_PATH))

try:
    from statute_index import StatuteIndex, IPC_TO_BNS, CRPC_TO_BNSS
    statute_index = StatuteIndex()
    # Reverse maps for facet labels: canonical BNS/BNSS tag -> legacy IPC/CrPC
    # number, so lawyers who still think in pre-2023 section numbers recognize
    # the option (e.g. "BNS s.103 (formerly IPC 302)").
    _BNS_TO_IPC = {v: k for k, v in IPC_TO_BNS.items()}
    _BNSS_TO_CRPC = {v: k for k, v in CRPC_TO_BNSS.items()}
    logger.info(f"✅ StatuteIndex loaded ({len(statute_index)} entries) from {STATUTE_INDEX_PATH}")
except Exception as e:
    # Broad except (not just ImportError): a missing dataset dir or any init
    # error must degrade to "normalization off", never crash app startup.
    logger.warning(f"⚠️ StatuteIndex unavailable — section normalization disabled: {e}")
    statute_index = None
    _BNS_TO_IPC = {}
    _BNSS_TO_CRPC = {}

# ----------------------------------------------------------------- normalization
# All five filterable fields are now facet-driven pickers, so the frontend
# already sends back exact canonical index values round-tripped from
# GET /api/facets. This normalization step stays as a safety net for any
# caller that bypasses the picker — a human (or API client) typing
# "Negotiable Instruments Act" or "302 IPC" still resolves to "NI" /
# "BNS s.103". A lookup on an already-canonical value is a no-op (resolves
# to itself), so it's safe to run unconditionally on checkbox-sourced input.
def _normalize_filters(filters: dict) -> dict:
    """Standardize free-text filter input to match OpenSearch index keys."""
    norm = filters.copy()

    if statute_index and "acts_cited" in norm and norm["acts_cited"]:
        standardized = []
        for a in norm["acts_cited"]:
            res = statute_index.lookup(a)
            standardized.append(res["act"] if res else a)
        norm["acts_cited"] = standardized

    # Standardize "302 IPC" -> "BNS s.103"
    if statute_index and "sections_cited" in norm and norm["sections_cited"]:
        standardized = []
        for s in norm["sections_cited"]:
            res = statute_index.lookup(s)
            standardized.append(res["canonical"] if res else s)
        norm["sections_cited"] = standardized

    return norm


# Acts/sections facets carry the bare canonical index values ("IPC", "BNS
# s.103") — fine for filtering, useless for a lawyer scanning checkboxes.
# Label them with the act's full name and, for sections that replaced an
# IPC/CrPC provision, the legacy number too.
def _act_label(code: str) -> str:
    if not statute_index:
        return code
    entry = statute_index.get_act_inventory_entry(code)
    return entry["display_name"] if entry and entry.get("display_name") else code


def _section_label(canonical: str) -> str:
    if canonical in _BNS_TO_IPC:
        return f"{canonical} (formerly IPC {_BNS_TO_IPC[canonical]})"
    if canonical in _BNSS_TO_CRPC:
        return f"{canonical} (formerly CrPC {_BNSS_TO_CRPC[canonical]})"
    return canonical


def _attach_facet_labels(facets: Facets) -> Facets:
    for fv in facets.acts_cited:
        fv.label = _act_label(str(fv.value))
    for fv in facets.sections_cited:
        fv.label = _section_label(str(fv.value))
    return facets


# ----------------------------------------------------------------- helpers
def _collect_filters(court, case_type, verdict, acts_cited, sections_cited,
                     bench_strength, year_from, year_to) -> dict:
    """Drop empties so the filter dict reflects only active selections."""
    raw = {
        "court": court, "case_type": case_type, "verdict": verdict,
        "acts_cited": acts_cited, "sections_cited": sections_cited,
        "bench_strength": bench_strength, "year_from": year_from, "year_to": year_to,
    }
    return {k: v for k, v in raw.items() if v}


def _hits_to_case_groups(hits: list) -> list:
    """Adapt OpenSearch's collapsed hits (one per case_id, top chunks carried
    in `inner_hits.top_chunks` — see opensearch_service.search()) into the
    shape _build_case_result expects. OpenSearch already did the chunk->case
    dedup and per-case chunk cap, so this is just a reshape, not a grouping."""
    groups = []
    for h in hits:
        src = h.get("_source", {})
        cid = src.get("case_id")
        if cid is None:
            continue
        inner = h.get("inner_hits", {}).get("top_chunks", {}).get("hits", {}).get("hits", [])
        chunks = [
            {
                "chunk_id": c["_source"].get("chunk_id"),
                "chunk_type": c["_source"].get("chunk_type"),
                "chunk_text": c["_source"].get("chunk_text"),
                "chunk_sequence": c["_source"].get("chunk_sequence"),
                "score": c.get("_score"),
            }
            for c in inner
        ]
        groups.append({"case_id": cid, "score": h.get("_score"), "src": src, "chunks": chunks})
    return groups


def _year_of(date_decided) -> Optional[int]:
    return int(str(date_decided)[:4]) if date_decided else None


def _build_case_result(group: dict, case_row: Optional[dict], bboxes: dict) -> CaseResult:
    src = group["src"]
    row = case_row or {}

    def pick(key, default=None):
        return row.get(key, src.get(key, default))

    date_decided = row.get("date_decided") or src.get("date_decided")
    chunks = [
        MatchedChunk(
            chunk_id=c["chunk_id"],
            chunk_type=c["chunk_type"],
            chunk_text=c["chunk_text"],
            chunk_sequence=c["chunk_sequence"],
            score=c["score"],
            page_range=(bboxes.get(c["chunk_id"]) or {}).get("page_range"),
            bbox=(bboxes.get(c["chunk_id"]) or {}).get("bbox"),
        )
        for c in group["chunks"]
    ]
    return CaseResult(
        case_id=group["case_id"],
        case_name=row.get("case_name") or src.get("parties") or "",
        citation=pick("citation"),
        court=pick("court"),
        case_type=pick("case_type"),
        verdict=pick("verdict"),
        year=_year_of(date_decided),
        date_decided=str(date_decided) if date_decided else None,
        bench=row.get("bench") or [],
        bench_strength=pick("bench_strength"),
        acts_cited=pick("acts_cited", []) or [],
        sections_cited=pick("sections_cited", []) or [],
        pdf_url=supabase_service.get_pdf_signed_url(group["case_id"]),
        score=group["score"],
        matched_chunks=chunks,
    )


# ------------------------------------------------------------------ /search
@router.get("/search", response_model=SearchResponse)
def search(
    q: Optional[str] = Query(None, alias="query", max_length=500, description="Semantic query; empty = filter-only"),
    court: Optional[List[str]] = Query(None),
    case_type: Optional[List[str]] = Query(None),
    verdict: Optional[List[str]] = Query(None),
    acts_cited: Optional[List[str]] = Query(None),
    sections_cited: Optional[List[str]] = Query(None),
    bench_strength: Optional[List[int]] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> SearchResponse:
    start = time.time()
    user_id = current_user.get("sub")
    q = (q or "").strip() or None
    filters = _collect_filters(court, case_type, verdict, acts_cited, sections_cited,
                               bench_strength, year_from, year_to)
    filters = _normalize_filters(filters)

    logger.info(f"🔍 Search Request - Query: '{q}', Filters: {filters}")

    try:
        if q:
            query_vector = embedding_service.embed_query(q)
            logger.info(f"✅ Embedding success - Vector dim: {len(query_vector)}")
        else:
            query_vector = None
            logger.info("ℹ️ No query provided - Filter-only mode")
    except Exception as e:
        logger.error(f"❌ query embedding failed: {e}", exc_info=True)
        query_vector = None

    try:
        # OpenSearch collapses chunk hits onto distinct case_ids itself (see
        # opensearch_service.search()) and paginates the collapsed result set
        # directly — `case_groups` below is already exactly this page, no
        # client-side slicing needed.
        hits, total_distinct_cases = opensearch_service.search(
            query_vector=query_vector, filters=filters, page=page, limit=limit
        )
        logger.info(f"📡 OpenSearch returned {len(hits)} cases (of {total_distinct_cases} matching)")
    except Exception as e:
        logger.error(f"❌ OpenSearch search failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="Search backend unavailable")

    case_groups = _hits_to_case_groups(hits)

    case_ids = [g["case_id"] for g in case_groups]
    chunk_ids = [c["chunk_id"] for g in case_groups for c in g["chunks"] if c["chunk_id"]]
    cases = supabase_service.get_cases_by_ids(case_ids)
    bboxes = supabase_service.get_chunk_bboxes_by_ids(chunk_ids)

    results = [_build_case_result(g, cases.get(g["case_id"]), bboxes) for g in case_groups]

    suppressed_raw = opensearch_service.suppressed_matches(
        query_vector=query_vector, filters=filters,
        result_case_ids=set(case_ids),
    )
    suppressed = [SuppressedCase(**s) for s in suppressed_raw]

    facets = _attach_facet_labels(Facets(**opensearch_service.facets(query_vector=query_vector, filters=filters)))

    took_ms = (time.time() - start) * 1000.0

    # Log the search DEFINITION (q + filters) — this is what history replays.
    supabase_service.log_search(
        search_id=str(uuid4()),
        query=q or "",
        results_count=total_distinct_cases,
        search_time_ms=took_ms,
        filters_applied=json.dumps(filters),
        user_id=user_id,
    )

    return SearchResponse(
        query=q,
        # Exact distinct-case count in both modes (cardinality agg scans every
        # matching doc; in semantic-query mode the kNN candidate pool is sized
        # to the exact matching-chunk count, not guessed — see
        # opensearch_service.search()). Only degrades to an approximate top-k
        # bound if the matching-chunk count exceeds KNN_K_CEILING.
        total_cases=total_distinct_cases,
        took_ms=round(took_ms, 1),
        results=results,
        facets=facets,
        suppressed=suppressed,
    )


# ------------------------------------------------------------------ /facets
@router.get("/facets", response_model=Facets)
def facets(
    q: Optional[str] = Query(None, max_length=500),
    court: Optional[List[str]] = Query(None),
    case_type: Optional[List[str]] = Query(None),
    verdict: Optional[List[str]] = Query(None),
    acts_cited: Optional[List[str]] = Query(None),
    sections_cited: Optional[List[str]] = Query(None),
    bench_strength: Optional[List[int]] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
) -> Facets:
    q = (q or "").strip() or None
    filters = _collect_filters(court, case_type, verdict, acts_cited, sections_cited,
                               bench_strength, year_from, year_to)
    filters = _normalize_filters(filters)
    try:
        query_vector = embedding_service.embed_query(q) if q else None
    except Exception as e:
        logger.warning(f"⚠️ facets embedding failed: {e}")
        query_vector = None
    return _attach_facet_labels(Facets(**opensearch_service.facets(query_vector=query_vector, filters=filters)))


# ----------------------------------------------------------------- /history
@router.get("/search/history", response_model=List[HistoryItem])
def get_search_history(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """Most-recent search definitions, de-duplicated by {query, filters}."""
    user_id = current_user.get("sub")
    rows = supabase_service.get_search_history(user_id, limit=200)
    out: List[HistoryItem] = []
    seen: set = set()
    for log in rows:
        query_val = log.get("query")
        filters_applied = log.get("filters_applied")
        key = (query_val or "", filters_applied or "")
        if key in seen:
            continue
        seen.add(key)
        try:
            parsed = json.loads(filters_applied) if filters_applied else {}
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        out.append(HistoryItem(query=query_val or None, filters=parsed, timestamp=log.get("created_at")))
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------ /health
@router.get("/search/health")
def search_health():
    healthy = opensearch_service.health_check()
    return {
        "service": "search",
        "status": "healthy" if healthy else "degraded",
        "opensearch": "connected" if healthy else "disconnected",
        "timestamp": datetime.now().isoformat(),
    }

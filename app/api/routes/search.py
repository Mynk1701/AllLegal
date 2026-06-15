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
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import SearchLog
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

logger = logging.getLogger(__name__)
router = APIRouter()


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


def _group_by_case(hits: list, max_chunks: int) -> list:
    """Collapse chunk hits into cases, preserving rank order; keep top-N chunks/case."""
    order: list = []
    by_case: dict = {}
    for h in hits:
        src = h.get("_source", {})
        cid = src.get("case_id")
        if cid is None:
            continue
        score = h.get("_score")
        if cid not in by_case:
            by_case[cid] = {"case_id": cid, "score": score, "src": src, "chunks": []}
            order.append(cid)
        entry = by_case[cid]
        if len(entry["chunks"]) < max_chunks:
            entry["chunks"].append({
                "chunk_id": src.get("chunk_id"),
                "chunk_type": src.get("chunk_type"),
                "chunk_text": src.get("chunk_text"),
                "chunk_sequence": src.get("chunk_sequence"),
                "score": score,
            })
    return [by_case[c] for c in order]


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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> SearchResponse:
    start = time.time()
    user_id = current_user.get("sub")
    q = (q or "").strip() or None
    filters = _collect_filters(court, case_type, verdict, acts_cited, sections_cited,
                               bench_strength, year_from, year_to)

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

    # Over-fetch chunks so grouping yields enough distinct cases for this page.
    needed = page * limit
    fetch_size = settings.KNN_K if query_vector is not None else max(
        settings.KNN_K, needed * settings.CHUNK_FETCH_FACTOR
    )

    try:
        hits = opensearch_service.search(query_vector=query_vector, filters=filters, size=fetch_size)
        logger.info(f"📡 OpenSearch returned {len(hits)} hits")
    except Exception as e:
        logger.error(f"❌ OpenSearch search failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="Search backend unavailable")

    grouped = _group_by_case(hits, settings.MAX_CHUNKS_PER_CASE)
    page_slice = grouped[(page - 1) * limit: page * limit]

    case_ids = [g["case_id"] for g in page_slice]
    chunk_ids = [c["chunk_id"] for g in page_slice for c in g["chunks"] if c["chunk_id"]]
    cases = supabase_service.get_cases_by_ids(case_ids)
    bboxes = supabase_service.get_chunk_bboxes_by_ids(chunk_ids)

    results = [_build_case_result(g, cases.get(g["case_id"]), bboxes) for g in page_slice]

    suppressed_raw = opensearch_service.suppressed_matches(
        query_vector=query_vector, filters=filters,
        result_case_ids={g["case_id"] for g in grouped},
    )
    suppressed = [SuppressedCase(**s) for s in suppressed_raw]

    facets = Facets(**opensearch_service.facets(query_vector=query_vector, filters=filters))

    took_ms = (time.time() - start) * 1000.0

    # Log the search DEFINITION (q + filters) — this is what history replays.
    try:
        db.add(SearchLog(
            search_id=str(uuid4()),
            query=q or "",
            results_count=len(grouped),
            search_time_ms=took_ms,
            filters_applied=json.dumps(filters),
            user_id=user_id,
        ))
        db.commit()
    except Exception as e:
        logger.error(f"❌ Error logging search: {e}")
        db.rollback()

    return SearchResponse(
        query=q,
        total_cases=len(grouped),
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
    try:
        query_vector = embedding_service.embed_query(q) if q else None
    except Exception as e:
        logger.warning(f"⚠️ facets embedding failed: {e}")
        query_vector = None
    return Facets(**opensearch_service.facets(query_vector=query_vector, filters=filters))


# ----------------------------------------------------------------- /history
@router.get("/search/history", response_model=List[HistoryItem])
def get_search_history(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Most-recent search definitions, de-duplicated by {query, filters}."""
    user_id = current_user.get("sub")
    rows = (
        db.query(SearchLog)
        .filter(SearchLog.user_id == user_id)
        .order_by(SearchLog.created_at.desc())
        .limit(200)
        .all()
    )
    out: List[HistoryItem] = []
    seen: set = set()
    for log in rows:
        key = (log.query or "", log.filters_applied or "")
        if key in seen:
            continue
        seen.add(key)
        try:
            parsed = json.loads(log.filters_applied) if log.filters_applied else {}
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        out.append(HistoryItem(query=log.query or None, filters=parsed, timestamp=log.created_at))
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

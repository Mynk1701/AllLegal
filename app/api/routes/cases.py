"""
Case detail route.

  GET /api/cases/{case_id}  full case record for the reader view: metadata,
  signed PDF URL, every chunk (with bbox/page_range), and outbound citations.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.schemas.schemas import CaseCitation, CaseDetail, MatchedChunk
from app.services.opensearch_service import opensearch_service
from app.services.supabase import supabase_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, current_user: dict = Depends(get_current_user)) -> CaseDetail:
    case_row = supabase_service.get_case_by_id(case_id)
    hits = opensearch_service.get_case_chunks(case_id)
    if not case_row and not hits:
        raise HTTPException(status_code=404, detail="Case not found")

    row = case_row or {}
    src0 = hits[0]["_source"] if hits else {}

    def pick(key, default=None):
        return row.get(key, src0.get(key, default))

    chunk_ids = [h["_source"].get("chunk_id") for h in hits if h["_source"].get("chunk_id")]
    bboxes = supabase_service.get_chunk_bboxes_by_ids(chunk_ids)

    chunks = [
        MatchedChunk(
            chunk_id=s.get("chunk_id"),
            chunk_type=s.get("chunk_type"),
            chunk_text=s.get("chunk_text"),
            chunk_sequence=s.get("chunk_sequence"),
            score=None,  # detail view is document order, not relevance-ranked
            page_range=(bboxes.get(s.get("chunk_id")) or {}).get("page_range"),
            bbox=(bboxes.get(s.get("chunk_id")) or {}).get("bbox"),
        )
        for s in (h["_source"] for h in hits)
    ]

    date_decided = row.get("date_decided") or src0.get("date_decided")
    cites = [CaseCitation(**c) for c in supabase_service.get_citations(case_id)]

    return CaseDetail(
        case_id=case_id,
        case_name=row.get("case_name") or src0.get("parties") or "",
        citation=pick("citation"),
        court=pick("court"),
        case_type=pick("case_type"),
        verdict=pick("verdict"),
        year=int(str(date_decided)[:4]) if date_decided else None,
        date_decided=str(date_decided) if date_decided else None,
        bench=row.get("bench") or [],
        bench_strength=pick("bench_strength"),
        acts_cited=pick("acts_cited", []) or [],
        sections_cited=pick("sections_cited", []) or [],
        pdf_url=supabase_service.get_pdf_signed_url(case_id),
        chunks=chunks,
        cites=cites,
    )

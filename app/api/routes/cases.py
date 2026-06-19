"""
Case detail route.

  GET /api/cases/{case_id}  full case record for the reader view: metadata,
  signed PDF URL, every chunk (with bbox/page_range), and outbound citations.
"""
import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.schemas.schemas import CaseCitation, CaseDetail, MatchedChunk
from app.services import case_index
from app.services.opensearch_service import opensearch_service
from app.services.supabase import supabase_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _derive_case_id(canonical_key: str) -> str:
    """case_id = sha256(normalized canonical key)[:10] — mirrors the pipeline's
    derive_case_id, so a cited_canonical_key resolves to the cited case's id."""
    return hashlib.sha256(" ".join(canonical_key.split()).lower().encode("utf-8")).hexdigest()[:10]


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

    # Resolve cited precedents that are in our corpus: a cited_canonical_key hashes
    # to the cited case's case_id (see _derive_case_id). Batch-check existence so
    # the reader can open the ones we have and show their names.
    raw_cites = supabase_service.get_citations(case_id)
    cand_ids = {
        _derive_case_id(c["cited_canonical_key"]): None
        for c in raw_cites
        if c.get("cited_canonical_key")
    }
    resolved = supabase_service.get_cases_by_ids(list(cand_ids)) if cand_ids else {}
    cites = []
    for c in raw_cites:
        key = c.get("cited_canonical_key")
        rid = _derive_case_id(key) if key else None
        hit = resolved.get(rid) if rid else None  # uploaded -> openable for real
        # Clickable if the cited case is in our dataset and isn't a self-reference:
        #   - in the uploaded 250 (hit)         -> openable, PDF loads
        #   - in the full 26k index (case_index) -> demo link (not loaded yet)
        in_dataset = rid is not None and rid != case_id and (hit is not None or case_index.known(rid))
        name = ((hit.get("case_name") if hit else None) or case_index.name_of(rid)) if in_dataset else None
        cites.append(
            CaseCitation(
                cited_canonical_key=key,
                relationship=c.get("relationship"),
                chunk_id=c.get("chunk_id"),
                cited_case_id=rid if in_dataset else None,
                cited_case_name=name,
                openable=bool(hit) and rid != case_id,
            )
        )

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

"""
Type-safe Pydantic schemas for API requests and responses.

Search is case-grouped: results are CASES, each carrying the top matching CHUNKS
(the highlight payload for the PDF reader). OpenSearch ranks/filters; Supabase
supplies case_name, bench, bbox/page_range, and the signed PDF URL.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime


# ==================== Search: chunk + case ====================

class MatchedChunk(BaseModel):
    """A matching chunk within a case — drives the highlighted PDF view."""
    chunk_id: str
    chunk_type: Optional[str] = Field(None, description="Rhetorical role (Ratio, FinalDecision, ...)")
    chunk_text: Optional[str] = None
    chunk_sequence: Optional[int] = None
    score: Optional[float] = Field(None, description="Semantic relevance (kNN); null for filter-only")
    page_range: Optional[List[int]] = Field(None, description="[min_page, max_page] (Supabase)")
    bbox: Optional[Any] = Field(None, description="List of per-block bounding boxes (Supabase)")


class CaseResult(BaseModel):
    """One case in the result list, with its top matching chunks."""
    case_id: str
    case_name: str = ""
    citation: Optional[str] = None
    court: Optional[str] = None
    case_type: Optional[str] = None
    verdict: Optional[str] = None
    year: Optional[int] = None
    date_decided: Optional[str] = None
    bench: List[str] = Field(default_factory=list, description="Judge names (Supabase)")
    bench_strength: Optional[int] = None
    acts_cited: List[str] = Field(default_factory=list)
    sections_cited: List[str] = Field(default_factory=list)
    pdf_url: Optional[str] = Field(None, description="Signed Supabase Storage URL")
    score: Optional[float] = Field(None, description="Best matched-chunk score")
    matched_chunks: List[MatchedChunk] = Field(default_factory=list)


# ==================== Facets ====================

class FacetValue(BaseModel):
    value: Any
    count: int = Field(..., description="Distinct CASES (cardinality), not chunks")


class Facets(BaseModel):
    court: List[FacetValue] = Field(default_factory=list)
    case_type: List[FacetValue] = Field(default_factory=list)
    verdict: List[FacetValue] = Field(default_factory=list)
    acts_cited: List[FacetValue] = Field(default_factory=list)
    sections_cited: List[FacetValue] = Field(default_factory=list)
    bench_strength: List[FacetValue] = Field(default_factory=list)
    year_range: Dict[str, Optional[int]] = Field(default_factory=dict)


# ==================== Suppression ====================

class SuppressedCase(BaseModel):
    """A strong match hidden by the active hard filters."""
    case_id: str
    case_name: str = ""
    score: Optional[float] = None
    failing_filters: List[Dict[str, Any]] = Field(default_factory=list)


# ==================== Search response ====================

class SearchResponse(BaseModel):
    query: Optional[str] = None
    total_cases: int = 0
    took_ms: float = 0.0
    results: List[CaseResult] = Field(default_factory=list)
    facets: Facets = Field(default_factory=Facets)
    suppressed: List[SuppressedCase] = Field(
        default_factory=list, description="Populated only when query + filters coexist"
    )


# ==================== History ====================

class HistoryItem(BaseModel):
    query: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None


# ==================== Case detail ====================

class CaseCitation(BaseModel):
    cited_canonical_key: Optional[str] = None
    relationship: Optional[str] = None
    chunk_id: Optional[str] = None


class CaseDetail(BaseModel):
    case_id: str
    case_name: str = ""
    citation: Optional[str] = None
    court: Optional[str] = None
    case_type: Optional[str] = None
    verdict: Optional[str] = None
    year: Optional[int] = None
    date_decided: Optional[str] = None
    bench: List[str] = Field(default_factory=list)
    bench_strength: Optional[int] = None
    acts_cited: List[str] = Field(default_factory=list)
    sections_cited: List[str] = Field(default_factory=list)
    pdf_url: Optional[str] = None
    chunks: List[MatchedChunk] = Field(default_factory=list)
    cites: List[CaseCitation] = Field(default_factory=list)


# ==================== Authentication Schemas ====================

class LoginRequest(BaseModel):
    """Schema for login request"""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")


class SignUpRequest(BaseModel):
    """Schema for sign up request"""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")


class AuthResponse(BaseModel):
    """Schema for authentication response"""
    access_token: str = Field(..., description="JWT access token")
    user_id: str = Field(..., description="User ID")
    message: str = Field(default="Authentication successful")


# ==================== Error Response ====================

class ErrorResponse(BaseModel):
    """Schema for error responses"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error details")
    status_code: int = Field(...)

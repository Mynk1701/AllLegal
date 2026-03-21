"""
Search API routes.
Main endpoint: GET /api/search
"""
from fastapi import APIRouter, Query, HTTPException, Header
from typing import Optional
from datetime import datetime
import logging
import time
from app.schemas.schemas import SearchResponse, CaseResponse
from app.services.supabase import supabase_service
from app.services.opensearch import opensearch_service

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== Hardcoded Mock Data (For Testing) ====================
# This data is returned when OpenSearch is not available
MOCK_CASES = [
    {
        "case_id": "case_001",
        "title": "State of Karnataka v. Rishikesh",
        "court": "Supreme Court of India",
        "year": 2015,
        "judge": "Justice R.K. Agarwal",
        "summary": "Constitutional validity of right to privacy and personal liberty under Article 21.",
        "case_number": "Civil Appeal No. 5555 of 2015"
    },
    {
        "case_id": "case_002",
        "title": "Right to Information v. Government of India",
        "court": "High Court of Delhi",
        "year": 2018,
        "judge": "Justice Manmohan",
        "summary": "Public's right to access government information and transparency in administrative operations.",
        "case_number": "Writ Petition (Civil) No. 8888 of 2018"
    },
    {
        "case_id": "case_003",
        "title": "Constitutional Rights - Fundamental Rights Case",
        "court": "Supreme Court of India",
        "year": 2020,
        "judge": "Justice D.Y. Chandrachud",
        "summary": "Comprehensive interpretation of Articles 12-35 defining fundamental rights and freedoms.",
        "case_number": "Petition (Civil) No. 2020-CC-12345"
    }
]

# ==================== Search Endpoint ====================

@router.get("/search", response_model=SearchResponse)
async def search(
    query: str = Query(
        ...,
        min_length=1,
        max_length=500,
        description="Search query (e.g., 'constitution', 'privacy', 'rights')"
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results (1-100)"
    ),
    authorization: Optional[str] = Header(None)
) -> SearchResponse:
    """
    🔍 Search for legal cases using boolean queries.
    
    **Currently returns hardcoded mock data for testing.**
    Will be integrated with OpenSearch for real searches.
    
    ### Parameters:
    - `query` (required): Search term
      - Examples: "constitution", "privacy", "right to life"
    - `limit` (optional): Max results to return (default: 10)
    - `Authorization` (optional): Bearer token for authenticated search logging
    
    ### Response:
    Returns matching legal cases sorted by relevance score.
    
    ### Examples:
    ```
    GET /api/search?query=constitution&limit=10
    GET /api/search?query=privacy%20rights
    ```
    """
    start_time = time.time()
    user_id = None
    
    try:
        logger.info(f"🔍 Search query received: '{query}' (limit: {limit})")
        
        # Optional: Verify authentication token
        if authorization:
            try:
                token = authorization.replace("Bearer ", "")
                payload = supabase_service.verify_token(token)
                if payload:
                    user_id = payload.get('sub')
                    logger.info(f"👤 Authenticated user: {user_id}")
            except Exception as e:
                logger.warning(f"⚠️  Token verification failed: {str(e)}")
                # Continue with unauthenticated search
        
        # ==================== HARDCODED RESPONSE ====================
        # TODO: Replace with real OpenSearch search
        # For now, return mock data for testing
        
        results = [
            CaseResponse(
                case_id=case["case_id"],
                title=case["title"],
                court=case["court"],
                year=case["year"],
                judge=case.get("judge"),
                summary=case.get("summary"),
                case_number=case.get("case_number"),
                relevance_score=0.95 if i == 0 else (0.87 if i == 1 else 0.92),
            )
            for i, case in enumerate(MOCK_CASES[:limit])
        ]
        
        search_time_ms = (time.time() - start_time) * 1000
        
        # Log search for analytics
        try:
            supabase_service.log_search(
                user_id=user_id or "anonymous",
                query=query,
                results_count=len(results),
                search_time_ms=search_time_ms
            )
        except Exception as e:
            logger.warning(f"⚠️  Could not log search: {str(e)}")
        
        response = SearchResponse(
            query=query,
            total_results=len(results),
            results=results,
            search_time_ms=search_time_ms,
            timestamp=datetime.now()
        )
        
        logger.info(f"✅ Search completed in {search_time_ms:.2f}ms with {len(results)} results")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error during search: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Search operation failed"
        )

# ==================== Health Check ====================

@router.get("/health")
async def search_health():
    """
    ❤️ Health check for search service.
    Verifies OpenSearch and Supabase connectivity.
    """
    opensearch_healthy = opensearch_service.health_check()
    
    return {
        "service": "search",
        "status": "healthy" if opensearch_healthy else "degraded",
        "opensearch": "✅ connected" if opensearch_healthy else "❌ disconnected",
        "timestamp": datetime.now().isoformat()
    }

from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    """
    Type-safe application configuration using Pydantic.
    Reads from .env file automatically.
    """
    
    # Application
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # OpenSearch Configuration (chunk-level index `case_chunks`)
    OPENSEARCH_HOST: str = "localhost"
    OPENSEARCH_PORT: int = 9200
    OPENSEARCH_USE_SSL: bool = False        # True for AWS OpenSearch (prod)
    OPENSEARCH_VERIFY_CERTS: bool = False   # True in prod
    OPENSEARCH_USER: str = ""               # empty for dev (security plugin off)
    OPENSEARCH_PASSWORD: str = ""
    OPENSEARCH_INDEX: str = "case_chunks"   # alias -> case_chunks_v1

    # Voyage AI embeddings — MUST match the model used at index time.
    # stage_04_embed.py indexed with voyage-law-2 + input_type="document";
    # queries are the asymmetric counterpart: input_type="query".
    VOYAGE_API_KEY: str = ""
    VOYAGE_MODEL: str = "voyage-law-2"

    # kNN / faceting knobs
    KNN_K: int = 200            # suppressed_matches() scan depth only — NOT the main /search
                                # candidate pool, which is now sized exactly per-request (see
                                # opensearch_service.search(), KNN_K_CEILING)
    FACET_POOL_K: int = 500     # candidate pool size that query-aware facets aggregate over
    FACET_TERMS_SIZE: int = 50  # max distinct values returned per facet

    # PDF storage (Google Cloud Storage — moved off Supabase, whose storage
    # tier is smaller than the PDF corpus; see HANDOVER.md). No pdf column on
    # `cases`; resolve by convention: <GCS_BUCKET>/<case_id>.pdf -> signed URL
    # (Option 1). Signed via HMAC interoperability creds (a user-account HMAC
    # key, not a service-account key — an org policy on the GCP project blocks
    # service-account keys, including HMAC ones, for this project).
    GCS_BUCKET: str = "law-helper-case-pdfs"
    GCS_HMAC_ACCESS_KEY: str = ""
    GCS_HMAC_SECRET_KEY: str = ""
    PDF_PATH_TEMPLATE: str = "{case_id}.pdf"
    PDF_SIGNED_URL_EXPIRY: int = 3600       # seconds

    # Result shaping
    MAX_CHUNKS_PER_CASE: int = 3            # top matching chunks shown per case (collapse inner_hits size)
    # kNN candidate pool (k) for /search is sized to the EXACT count of chunks
    # matching the active filters (a cheap _count call, ~20-50ms) — not
    # guessed via a multiplier. That makes k cover every real candidate
    # whenever the filtered set fits under this ceiling, so OpenSearch's
    # `collapse` can surface every distinct case with no shortfall (verified
    # through page 5 of a 50-case corpus). Only falls back to an approximate
    # top-k once the matching set exceeds the ceiling — a deliberately huge,
    # unfiltered, full-corpus query. See opensearch_service.search().
    #
    # Sized against Lucene-HNSW latency on the 465k-chunk corpus: k scales the
    # candidate pool an unfiltered query walks, so warm /search latency is ~linear
    # in this ceiling (k=5000 ~3.3s, k=1500 ~1.7s, k=500 ~0.8s, measured). 1500
    # covers ~500 distinct cases at 3 chunks/case — far deeper than real
    # pagination — while keeping every unfiltered query comfortably under the
    # client read timeout even when the OS page cache is cold. Raise only if
    # deep-pagination recall on huge unfiltered result sets matters more than tail
    # latency (and give the VM more RAM for page cache first).
    KNN_K_CEILING: int = 1500

    # Supabase/Auth Configuration
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # CORS
    # Every browser origin that may call this API. A missing origin here surfaces
    # as a CORS error in the browser console while curl/Postman still work — so
    # add the new host BEFORE pointing DNS at it, not after.
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "https://nirnaylegal.in",
        "https://www.nirnaylegal.in",
        # Vercel's generated URL — kept so preview/rollback deploys keep working.
        "https://frontend-seven-tau-89.vercel.app",
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses @lru_cache to ensure single instance across app.
    """
    return Settings()

settings = get_settings()
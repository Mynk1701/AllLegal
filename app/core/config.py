from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    """
    Type-safe application configuration using Pydantic.
    Reads from .env file automatically.
    """
    
    # Application
    APP_NAME: str = "AllLegal"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database (PostgreSQL with Supabase)
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/alllegal"

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
    KNN_K: int = 200            # semantic neighbours pulled per search (pre-grouping)
    FACET_POOL_K: int = 500     # candidate pool size that query-aware facets aggregate over
    FACET_TERMS_SIZE: int = 50  # max distinct values returned per facet

    # PDF storage (Supabase Storage). No pdf column on `cases`; resolve by
    # convention: <PDF_BUCKET>/<case_id>.pdf -> signed URL (Option 1).
    PDF_BUCKET: str = "case_pdfs"
    PDF_PATH_TEMPLATE: str = "{case_id}.pdf"
    PDF_SIGNED_URL_EXPIRY: int = 3600       # seconds

    # Result shaping
    MAX_CHUNKS_PER_CASE: int = 3            # top matching chunks shown per case
    CHUNK_FETCH_FACTOR: int = 8             # over-fetch chunks so grouping yields enough cases

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Supabase/Auth Configuration
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    
    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    API_KEY: str = "dev-api-key"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
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
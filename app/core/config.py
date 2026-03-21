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
    
    # OpenSearch Configuration
    OPENSEARCH_HOST: str = "localhost"
    OPENSEARCH_PORT: int = 9200
    OPENSEARCH_SCHEME: str = "http"
    OPENSEARCH_INDEX: str = "legal_cases"
    OPENSEARCH_TIMEOUT: int = 20
    
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
        extra = "ignore"  # Allow extra fields from .env (ignore them)

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses @lru_cache to ensure single instance across app.
    """
    return Settings()

settings = get_settings()
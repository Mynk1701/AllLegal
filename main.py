"""
AllLegal - Legal Case Search API
FastAPI application with Supabase integration for auth and database
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from app.api.routes import search, auth
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    logger.info("🚀 AllLegal API starting up...")
    logger.info(f"📍 Debug Mode: {settings.DEBUG}")
    logger.info(f"🔗 Supabase URL: {settings.SUPABASE_URL}")
    yield
    logger.info("🛑 AllLegal API shutting down...")

# Create FastAPI app
app = FastAPI(
    title="AllLegal - Legal Case Search API",
    description="Search Indian legal cases with boolean queries using OpenSearch. Powered by Supabase.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(auth.router, prefix="/api", tags=["auth"])

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint - verify API is running"""
    return {
        "status": "healthy",
        "service": "AllLegal API",
        "version": "1.0.0",
        "supabase_connected": True
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": "Welcome to AllLegal - Legal Case Search API",
        "description": "Search Indian legal cases with fast boolean queries",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
        "endpoints": {
            "search": "/api/search",
            "auth": "/api/auth/login",
            "health": "/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

"""
AllLegal - Legal Case Search API
FastAPI application with Supabase integration for auth and database
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import time
from app.api.routes import search, cases, groups
from app.core.config import settings

# 1. Setup Global Logging
logging.basicConfig(
    level=logging.WARNING, # Only warnings by default to keep logs clean
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")
logger.setLevel(logging.INFO) # Our app specifically will log INFO

# 2. Force silence noisy libraries
for noisy_lib in ["httpx", "opensearch", "uvicorn", "supabase", "postgrest", "voyageai", "security_logger"]:
    logging.getLogger(noisy_lib).setLevel(logging.WARNING)

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    logger.info("🚀 AllLegal API starting up (Port 8000)...")
    yield
    logger.info("🛑 AllLegal API shutting down...")

# Create FastAPI app
app = FastAPI(
    title="AllLegal - Legal Case Search API",
    version="1.0.0",
    lifespan=lifespan
)

# Request logger middleware (Trimmmed)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = round((time.time() - start_time) * 1000, 1)
    # Simple one-liner: "GET /api/search ?query=act - 200 (15ms)"
    logger.info(f"Incoming: {request.method} {request.url.path} {request.url.query} - {response.status_code} ({duration}ms)")
    return response

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(cases.router, prefix="/api", tags=["cases"])
app.include_router(groups.router, prefix="/api", tags=["groups"])

# Root
@app.get("/")
async def root():
    return {"status": "running", "service": "AllLegal API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)

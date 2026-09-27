import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.api import jobs, assets, metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("jate_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing JATE Backend Services...")
    # Verify storage directory exists
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    # Test database connectivity
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection successfully established.")
    except Exception as e:
        logger.error(f"Database connection error: {e}")
    yield
    logger.info("Shutting down JATE Backend Services...")
    await engine.dispose()


app = FastAPI(
    title="JATE - Automated Job Acquisition & Tracking Engine",
    description="High-velocity automated job ingestion, LLM-tailoring, and application execution platform.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS Middleware for Coolify and local environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

# Mount API Routers
app.include_router(jobs.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")


@app.get("/api/health", tags=["Health"])
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "JATE Backend",
        "timestamp": datetime.utcnow().isoformat(),
        "storage_dir": settings.STORAGE_DIR
    }

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.models import ORGANIZATION_EXPRESSION
from app.config import settings
from app.database import engine
from app.api import jobs, assets, metrics, candidate
from app.services.candidate_profile import initialize_candidate_schema

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
            await conn.execute(text("SELECT pg_advisory_xact_lock(74822026)"))
            await conn.execute(text(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS organization_type VARCHAR(20) "
                f"GENERATED ALWAYS AS ({ORGANIZATION_EXPRESSION}) STORED"
            ))
            await initialize_candidate_schema(conn)
        logger.info("Database connection successfully established.")
    except Exception as e:
        logger.exception("Database initialization failed")
        raise
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
app.include_router(candidate.router, prefix="/api")


@app.get("/api/health", tags=["Health"])
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "JATE Backend",
        "timestamp": datetime.utcnow().isoformat(),
        "storage_dir": settings.STORAGE_DIR
    }

"""
FastAPI application entry point.
OCR Plagiarism Detection Backend API.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, get_db, SessionLocal
from app.routes import analyze_router
from app.schemas.analysis import HealthResponse
from app.seed import seed_database

# Configure logging to show all debug messages
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

# Set specific loggers
logging.getLogger("app").setLevel(logging.DEBUG)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)  # Reduce SQL noise

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initializes database and seeds data on startup.
    """
    # Startup: Initialize database and seed
    print("Initializing database...")
    init_db()

    # Seed with sample documents
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

    print("Application startup complete.")
    yield

    # Shutdown: Cleanup if needed
    print("Application shutdown.")


# Create the FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## OCR Plagiarism Detection API

    A backend service for detecting plagiarism in text extracted from document images.

    ### Features:
    - **Text Analysis**: Compare submitted text against a repository of academic documents
    - **Similarity Scoring**: Uses TF-IDF vectorization and Cosine Similarity
    - **Configurable Thresholds**: Adjustable plagiarism detection sensitivity
    - **Top Matches**: Returns the most similar documents with their scores

    ### Workflow:
    1. Mobile app captures document image
    2. OCR extracts text from the image
    3. Text is sent to this API via POST /api/analyze
    4. API returns similarity scores and plagiarism verdict
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware for Android app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(analyze_router)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with welcome message."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    Verifies the application and database are operational.
    """
    from sqlalchemy import text

    # Test database connection
    db_connected = True
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_connected = False

    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        database_connected=db_connected,
    )

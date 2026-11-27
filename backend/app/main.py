import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import ai, runs
from app.core.config import settings
from app.core.database import Base, engine
from app.models import ai_analysis, optimization_run  # noqa: F401  (register tables)

logging.basicConfig(level=logging.INFO)

# Dev convenience. In the integrated system use Alembic migrations instead.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.1.0",
    description="WasteFlow AI Intelligence Layer (Spec v1.0)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,   # Spec 8.1: restrict CORS
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(ai.router, prefix=settings.API_V1_STR)
if settings.ENABLE_DEV_ENDPOINTS:
    app.include_router(runs.router, prefix=settings.API_V1_STR)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "ai_configured": bool(settings.GEMINI_API_KEY) or settings.AI_ALLOW_MOCK,
        "provider": "gemini" if settings.GEMINI_API_KEY else ("mock" if settings.AI_ALLOW_MOCK else None),
        "model": settings.GEMINI_MODEL,
        "prompt_version": settings.PROMPT_VERSION,
    }

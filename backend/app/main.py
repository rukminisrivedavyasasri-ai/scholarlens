import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.app.config import settings
from backend.app.database import engine, Base
import backend.app.models  # ensure all models are imported
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.collections import router as collections_router
from backend.app.api.v1.documents import router as documents_router
from backend.app.api.v1.audit import router as audit_router
from backend.app.api.v1.qa import router as qa_router
from backend.app.api.v1.extractions import router as extractions_router
from backend.app.api.v1.comparison import router as comparison_router
from backend.app.api.v1.board import router as board_router

from backend.app.services.embedding_service import embedding_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Preload and pre-warm embedding model once at startup
    embedding_service.preload_model()
    yield
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Research Reading and Evidence Workspace API with citation grounding, claim verification, and pre-retrieval ACL.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS setup
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(collections_router, prefix=settings.API_V1_STR)
app.include_router(documents_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(qa_router, prefix=settings.API_V1_STR)
app.include_router(extractions_router, prefix=settings.API_V1_STR)
app.include_router(comparison_router, prefix=settings.API_V1_STR)
app.include_router(board_router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "pre_retrieval_acl": "enforced",
        "version": "1.0.0"
    }

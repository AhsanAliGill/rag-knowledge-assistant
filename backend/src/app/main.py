from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from app.core.config import settings
from app.db.session import engine
from app.routers.auth import router as auth_router
from app.routers.conversations import router as rag_conversations_router
from app.routers.documents import router as rag_documents_router
from app.routers.evaluation import router as rag_evaluation_router
from app.routers.query import router as rag_query_router
from app.services.config.logging_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(rag_documents_router, prefix="/api/v1")
app.include_router(rag_query_router, prefix="/api/v1")
app.include_router(rag_evaluation_router, prefix="/api/v1")
app.include_router(rag_conversations_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

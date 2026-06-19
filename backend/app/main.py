from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.quote_agent import setup_langfuse_observability
from app.api.routes import emails, quotes, search
from app.config import settings
from app.db import close_pool


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_langfuse_observability()
    yield
    await close_pool()


app = FastAPI(
    title="Boss API",
    description="Automatisation des demandes de prix — Agent IA + RAG pgvector",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api/v1")
app.include_router(emails.router, prefix="/api/v1")
app.include_router(quotes.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str | bool]:
    uses_mistral = settings.llm_model.startswith("mistral") or settings.embedding_provider == "mistral"
    return {
        "status": "ok",
        "service": "boss-api",
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "mistral_configured": bool(settings.mistral_api_key),
        "openai_configured": bool(settings.openai_api_key),
        "ai_ready": bool(settings.mistral_api_key) if uses_mistral else bool(settings.openai_api_key),
        "catalog_xlsx_present": settings.catalog_xlsx_path.is_file(),
        "docx_template_present": settings.docx_template_path.is_file(),
    }

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import analytics, auth, chat, documents, sessions
from app.config import get_settings
from app.core.logging import configure_logging, request_logging_middleware
from app.database import init_db
from app.schemas import AppInfo

settings = get_settings()
configure_logging(settings.debug)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if settings.demo_mode:
        from app.database import AsyncSessionLocal
        from app.demo import purge_stale_guests, seed_demo_content

        async with AsyncSessionLocal() as db:
            try:
                await purge_stale_guests(db)
                await seed_demo_content(db)
            except Exception:
                logging.getLogger("synapse").exception("demo seeding failed")
    yield


app = FastAPI(
    title=settings.app_name,
    description="An agentic AI assistant platform with tool use, hybrid RAG and streaming.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_logging_middleware)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(sessions.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(analytics.router, prefix=settings.api_prefix)


@app.get(f"{settings.api_prefix}/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get(f"{settings.api_prefix}/info", response_model=AppInfo, tags=["meta"])
async def info() -> AppInfo:
    return AppInfo(
        name=settings.app_name,
        default_model=settings.chat_model,
        available_models=settings.model_list,
        rag_enabled=True,
        demo_mode=settings.demo_mode,
        demo_messages_per_hour=(
            settings.demo_messages_per_hour if settings.demo_mode else None
        ),
        repo_url=settings.demo_banner_repo_url if settings.demo_mode else None,
    )


_dist = Path(__file__).resolve().parent.parent / "static"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")

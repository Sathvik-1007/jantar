import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from jantar.api.routes import agent, health
from jantar.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load ML models at startup so first request is fast."""
    from jantar.rag.embeddings import warmup_embeddings
    from jantar.rag.reranker import warmup_reranker

    logger.info("Warming up models...")
    warmup_embeddings()
    warmup_reranker()
    logger.info("Models ready.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Jantar", description="Agentic Layer for Indian Government Services", lifespan=lifespan)

    @app.middleware("http")
    async def log_and_auth_middleware(request: Request, call_next):
        t0 = time.perf_counter()
        path = request.url.path
        method = request.method

        # Skip auth for health/docs
        if path in ("/health", "/docs", "/openapi.json"):
            response = await call_next(request)
            logger.debug("%s %s %d %.3fs", method, path, response.status_code, time.perf_counter() - t0)
            return response

        # Auth check. Fail closed: if no API key is configured, deny every
        # request (an empty configured key must NOT match an empty header).
        api_key = request.headers.get("x-api-key", "")
        if not settings.api_key or not secrets.compare_digest(api_key, settings.api_key):
            logger.warning("Auth failed | path=%s ip=%s", path, request.client.host if request.client else "unknown")
            return JSONResponse(status_code=401, content={"error": "Invalid or missing API key."})

        response = await call_next(request)
        elapsed = time.perf_counter() - t0
        logger.info("%s %s %d %.2fs", method, path, response.status_code, elapsed)
        return response

    app.include_router(health.router)
    app.include_router(agent.router)
    return app

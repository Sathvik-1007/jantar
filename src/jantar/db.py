"""Shared database clients — single source of truth."""

from functools import lru_cache

from qdrant_client import QdrantClient

from jantar.config import settings


@lru_cache(maxsize=1)
def get_qdrant() -> QdrantClient:
    """Singleton Qdrant client. Reuses connection across the application."""
    return QdrantClient(url=settings.qdrant_url, check_compatibility=False)

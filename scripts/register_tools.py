#!/usr/bin/env python3
"""Register tool specs into Qdrant tool_vectors collection.

This is the PRIMARY tool ingestion pipeline. Reads all JSON specs from
data/tool_specs/ and embeds them (dense + sparse via BGE-M3) into Qdrant.

Usage:
    python scripts/register_tools.py          # register all specs
    python scripts/register_tools.py --reset  # delete collection first, then register

The Colab script (colab_ingest.py) is a SUPPLEMENTARY path for bulk-indexing
the 137K+ data.gov.in catalog. This script handles the core custom tool specs
that the adapters actually execute.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from pathlib import Path

# Ensure jantar package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jantar.config import settings  # noqa: E402
from jantar.db import get_qdrant  # noqa: E402
from jantar.models import ToolDescriptor  # noqa: E402
from jantar.rag.embeddings import embed_dense_and_sparse  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

TOOL_COLLECTION = "tool_vectors"
TOOL_SPECS_DIR = Path(__file__).resolve().parent.parent / "data" / "tool_specs"
VECTOR_DIM = 1024


def ensure_collection(client, reset: bool = False) -> None:
    """Create the tool_vectors collection if it doesn't exist."""
    from qdrant_client.models import (
        Distance,
        SparseIndexParams,
        SparseVectorParams,
        VectorParams,
    )

    collections = [c.name for c in client.get_collections().collections]

    if TOOL_COLLECTION in collections:
        if reset:
            client.delete_collection(TOOL_COLLECTION)
            logger.info("Deleted existing '%s' collection.", TOOL_COLLECTION)
        else:
            info = client.get_collection(TOOL_COLLECTION)
            logger.info(
                "Collection '%s' exists (%d points). Upserting specs alongside existing data.",
                TOOL_COLLECTION,
                info.points_count,
            )
            return

    client.create_collection(
        collection_name=TOOL_COLLECTION,
        vectors_config={"dense": VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams())},
    )
    logger.info("Created '%s' collection.", TOOL_COLLECTION)


def build_search_text(spec: ToolDescriptor) -> str:
    """Build the text that gets embedded for retrieval.

    Combines contextual_description (rich) + examples for better recall.
    """
    parts = [f"{spec.name}: {spec.contextual_description or spec.description}"]
    if spec.examples:
        parts.append(f"Examples: {'; '.join(spec.examples[:5])}")
    return " ".join(parts)


def register_all(reset: bool = False) -> int:
    """Load all tool specs from data/tool_specs/ and upsert into Qdrant."""
    from qdrant_client.models import PointStruct, SparseVector

    if not TOOL_SPECS_DIR.exists():
        logger.error("Tool specs directory not found: %s", TOOL_SPECS_DIR)
        return 0

    spec_files = sorted(TOOL_SPECS_DIR.glob("*.json"))
    if not spec_files:
        logger.error("No .json files found in %s", TOOL_SPECS_DIR)
        return 0

    # Validate all specs first
    specs: list[ToolDescriptor] = []
    for f in spec_files:
        try:
            data = json.loads(f.read_text())
            spec = ToolDescriptor(**data)
            specs.append(spec)
        except Exception as e:
            logger.error("Invalid spec %s: %s", f.name, e)
            continue

    logger.info("Loaded %d valid tool specs.", len(specs))

    # Connect to Qdrant
    client = get_qdrant()
    ensure_collection(client, reset=reset)

    # Build search texts and embed
    texts = [build_search_text(s) for s in specs]
    logger.info("Embedding %d tool descriptions with BGE-M3...", len(texts))
    dense_vecs, sparse_vecs = embed_dense_and_sparse(texts)

    # Upsert into Qdrant
    points = []
    for i, spec in enumerate(specs):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, spec.name))
        payload = {
            "tool_name": spec.name,
            "name": spec.name,
            "description": spec.description,
            "contextual_description": spec.contextual_description,
            "domain": spec.domain,
            "source": spec.base_url,
            "endpoint": spec.endpoint,
            "auth_method": spec.auth_method,
            "http_method": spec.http_method,
            "input_schema": spec.input_schema,
            "examples": spec.examples,
            "rate_limit": spec.rate_limit,
        }
        points.append(
            PointStruct(
                id=point_id,
                vector={
                    "dense": dense_vecs[i],
                    "sparse": SparseVector(
                        indices=sparse_vecs[i]["indices"],
                        values=sparse_vecs[i]["values"],
                    ),
                },
                payload=payload,
            )
        )

    client.upsert(collection_name=TOOL_COLLECTION, points=points)
    logger.info("Registered %d tools in '%s'.", len(points), TOOL_COLLECTION)
    for spec in specs:
        logger.info("  ✓ %s (%s)", spec.name, spec.domain)

    return len(points)


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    count = register_all(reset=reset)
    if count:
        logger.info("Done. %d tools ready for RAG.", count)
    else:
        logger.error("No tools registered. Check data/tool_specs/ directory.")
        sys.exit(1)

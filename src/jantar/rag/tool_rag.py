from __future__ import annotations

import logging
import time
from typing import Any

from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    SparseVector,
)

from jantar.db import get_qdrant
from jantar.models import ToolDescriptor
from jantar.rag.embeddings import embed_dense_and_sparse
from jantar.rag.hybrid import reciprocal_rank_fusion
from jantar.rag.reranker import rerank

logger = logging.getLogger(__name__)
TOOL_COLLECTION = "tool_vectors"


async def select_tool(query: str, domain: str | None = None, top_k: int = 1) -> list[dict[str, Any]]:
    """Full tool selection RAG pipeline: hybrid retrieve → RRF → rerank → return best tool(s).

    NEVER raises — returns empty list on any failure (network, Qdrant down, etc.)
    """
    t0 = time.perf_counter()
    try:
        client = get_qdrant()

        # 1. Embed query (dense + sparse in single forward pass)
        dense_vecs, sparse_vecs = embed_dense_and_sparse([query])
        dense_vec = dense_vecs[0]
        sparse_vec = sparse_vecs[0]

        # 2. Domain filter (hierarchical routing)
        search_filter = None
        if domain:
            search_filter = Filter(must=[FieldCondition(key="domain", match=MatchValue(value=domain))])

        # 3. Dense search
        dense_results = client.query_points(
            collection_name=TOOL_COLLECTION,
            query=dense_vec,
            using="dense",
            limit=50,
            query_filter=search_filter,
        )
        dense_ranked = [(p.id, p.score) for p in dense_results.points]

        # 4. Sparse search
        sparse_results = client.query_points(
            collection_name=TOOL_COLLECTION,
            query=SparseVector(indices=sparse_vec["indices"], values=sparse_vec["values"]),
            using="sparse",
            limit=50,
            query_filter=search_filter,
        )
        sparse_ranked = [(p.id, p.score) for p in sparse_results.points]

        # 5. RRF fusion
        fused = reciprocal_rank_fusion([dense_ranked, sparse_ranked])
        top_50_ids = [doc_id for doc_id, _ in fused[:50]]

        if not top_50_ids:
            logger.warning("Tool RAG | query=%r — no candidates found", query[:60])
            return []

        # 6. Fetch payloads for reranking
        points = client.retrieve(collection_name=TOOL_COLLECTION, ids=top_50_ids, with_payload=True)
        id_to_payload = {p.id: p.payload for p in points}

        # 7. Rerank with cross-encoder
        def _rerank_text(payload: dict) -> str:
            """Get best text for reranking — works with both tool specs and catalog entries."""
            return (
                payload.get("contextual_description")
                or payload.get("description")
                or payload.get("title")
                or ""
            )

        docs_for_rerank = [_rerank_text(id_to_payload.get(did, {})) for did in top_50_ids]
        reranked = rerank(query, docs_for_rerank, top_k=top_k)

        # 8. Return top tools
        results = []
        for idx, score in reranked:
            tool_id = top_50_ids[idx]
            payload = id_to_payload.get(tool_id, {})
            results.append({"id": tool_id, "score": score, **payload})

        elapsed = time.perf_counter() - t0
        top_name = (results[0].get("tool_name") or results[0].get("name")
                    or results[0].get("title", "none")[:50]) if results else "none"
        logger.info(
            "Tool RAG | query=%r domain=%s results=%d top=%s score=%.4f elapsed=%.3fs",
            query[:60], domain, len(results), top_name,
            results[0]["score"] if results else 0, elapsed,
        )
        return results

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("Tool RAG failed | query=%r error=%s elapsed=%.3fs", query[:60], e, elapsed, exc_info=True)
        return []

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
from jantar.rag.embeddings import embed_dense_and_sparse
from jantar.rag.hybrid import reciprocal_rank_fusion
from jantar.rag.reranker import rerank

logger = logging.getLogger(__name__)
KNOWLEDGE_COLLECTION = "knowledge_vectors"


async def retrieve_knowledge(query: str, domain: str | None = None, top_k: int = 5) -> list[dict[str, Any]]:
    """Full knowledge RAG pipeline: hybrid → RRF → rerank → parent expand → cite.

    NEVER raises — returns empty list on any failure (network, Qdrant down, etc.)
    """
    t0 = time.perf_counter()
    try:
        client = get_qdrant()

        # 1. Embed query (dense + sparse in single forward pass)
        dense_vecs, sparse_vecs = embed_dense_and_sparse([query])
        dense_vec = dense_vecs[0]
        sparse_vec = sparse_vecs[0]

        # 2. Optional domain filter
        search_filter = None
        if domain:
            search_filter = Filter(must=[FieldCondition(key="domain", match=MatchValue(value=domain))])

        # 3. Dense search on child chunks
        dense_results = client.query_points(
            collection_name=KNOWLEDGE_COLLECTION,
            query=dense_vec,
            using="dense",
            limit=50,
            query_filter=search_filter,
        )
        dense_ranked = [(str(p.id), p.score) for p in dense_results.points]

        # 4. Sparse search
        sparse_results = client.query_points(
            collection_name=KNOWLEDGE_COLLECTION,
            query=SparseVector(indices=sparse_vec["indices"], values=sparse_vec["values"]),
            using="sparse",
            limit=50,
            query_filter=search_filter,
        )
        sparse_ranked = [(str(p.id), p.score) for p in sparse_results.points]

        # 5. RRF fusion
        fused = reciprocal_rank_fusion([dense_ranked, sparse_ranked])
        top_50_ids = [doc_id for doc_id, _ in fused[:50]]

        if not top_50_ids:
            logger.warning("Knowledge RAG | query=%r — no candidates found", query[:60])
            return []

        # 6. Fetch child chunk payloads
        points = client.retrieve(collection_name=KNOWLEDGE_COLLECTION, ids=top_50_ids, with_payload=True)
        id_to_payload = {str(p.id): p.payload for p in points}

        # 7. Rerank children
        docs_for_rerank = [
            id_to_payload.get(did, {}).get("context_prefix", "") + " " + id_to_payload.get(did, {}).get("content", "")
            for did in top_50_ids
        ]
        reranked = rerank(query, docs_for_rerank, top_k=top_k)

        # 8. Parent expansion + citation
        results = []
        for idx, score in reranked:
            child_id = top_50_ids[idx]
            payload = id_to_payload.get(child_id, {})
            content = payload.get("parent_content", payload.get("content", ""))
            results.append({
                "content": content,
                "score": score,
                "citation": {
                    "source": payload.get("source_url", ""),
                    "title": payload.get("document_title", ""),
                    "section": payload.get("section_path", ""),
                    "effective_date": payload.get("effective_date", ""),
                },
            })

        elapsed = time.perf_counter() - t0
        logger.info(
            "Knowledge RAG | query=%r domain=%s dense=%d sparse=%d fused=%d results=%d top_score=%.4f elapsed=%.3fs",
            query[:60], domain, len(dense_ranked), len(sparse_ranked), len(fused),
            len(results), results[0]["score"] if results else 0, elapsed,
        )
        return results

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("Knowledge RAG failed | query=%r error=%s elapsed=%.3fs", query[:60], e, elapsed, exc_info=True)
        return []

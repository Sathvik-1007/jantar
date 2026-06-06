"""Cross-encoder reranker — BGE-reranker-v2-m3.

This is the precision stage of the RAG pipeline. After hybrid retrieval
(dense + sparse -> RRF) returns ~50 candidates, this cross-encoder reads each
(query, document) pair jointly and produces a relevance score far more
accurate than embedding cosine similarity alone.

BGE-reranker-v2-m3 is trained on top of BGE-M3, inheriting its strong
multilingual capability (100+ languages including all scheduled Indian
languages) while remaining a slim ~568M parameter model that fits on a 4GB
GPU with FP16.

Loaded via sentence-transformers' CrossEncoder, which uses the same BAAI model
weights and handles tokenization correctly on transformers 5.x. The heavy
import (torch / sentence-transformers) is performed lazily inside the loader so
that importing this module is cheap and unit tests can run without a GPU.

HuggingFace offline mode is configured in ``jantar.__init__`` at process
import time (before any HF library is imported), so no network calls are made
when the model is already cached.

Reference: https://huggingface.co/BAAI/bge-reranker-v2-m3
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

# Max combined token length for a (query, document) pair fed to the reranker.
_MAX_LENGTH = 512


@lru_cache(maxsize=1)
def _get_reranker() -> "CrossEncoder":
    """Load BGE-reranker-v2-m3 once (process-wide singleton).

    Uses CUDA when available, else CPU. The model is downloaded on first use
    if not cached; subsequent loads are fully offline (see ``jantar.__init__``).

    Returns:
        A ready-to-use ``CrossEncoder`` instance.
    """
    import logging
    import time

    import torch
    from sentence_transformers import CrossEncoder

    logger = logging.getLogger(__name__)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Loading BGE-reranker-v2-m3 on %s...", device)
    t0 = time.time()
    model = CrossEncoder("BAAI/bge-reranker-v2-m3", device=device, max_length=_MAX_LENGTH)
    logger.info("BGE-reranker-v2-m3 loaded in %.1fs", time.time() - t0)
    return model


def warmup_reranker() -> None:
    """Pre-load the reranker model. Call at app startup to avoid first-query latency."""
    _get_reranker()


def rerank(query: str, documents: list[str], top_k: int = 5) -> list[tuple[int, float]]:
    """Rerank documents by relevance to ``query`` using the cross-encoder.

    The cross-encoder reads (query, document) pairs jointly — it sees both
    texts together, enabling token-level interaction that bi-encoders miss.
    This is why it is more accurate but slower, hence applied only to a small
    candidate set produced by the initial hybrid retrieval.

    Args:
        query: The user's search query.
        documents: Candidate document texts to rerank.
        top_k: Number of top results to return.

    Returns:
        ``[(original_index, score), ...]`` sorted by relevance descending.
        Scores are sigmoid-normalized in the [0, 1] range. Returns an empty
        list when ``documents`` is empty.
    """
    if not documents:
        return []

    model = _get_reranker()
    pairs = [[query, doc] for doc in documents]
    scores = model.predict(pairs)

    indexed = [(i, float(s)) for i, s in enumerate(scores)]
    indexed.sort(key=lambda x: x[1], reverse=True)
    return indexed[:top_k]

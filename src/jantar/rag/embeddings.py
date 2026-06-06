"""BGE-M3 embedding module — dense + learned sparse vectors from one model.

Uses FlagEmbedding's BGEM3FlagModel which produces:
- Dense vectors: 1024-dim normalized embeddings for semantic similarity.
- Sparse vectors: Learned lexical weights (token_id → weight) for exact term matching.
  These are NOT fake BM25/TF-IDF — they are learned sparse representations trained
  end-to-end as part of BGE-M3's multi-functionality objective.

Both vector types are produced in a single forward pass through the model.
Supports 100+ languages including all 22 scheduled Indian languages.
Input length: up to 8192 tokens.

Reference: https://huggingface.co/BAAI/bge-m3
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from FlagEmbedding import BGEM3FlagModel

# Maximum batch size to avoid OOM on 4GB GPU.
_BATCH_SIZE = 12

# Maximum token length per input (BGE-M3 supports up to 8192).
_MAX_LENGTH = 8192


@lru_cache(maxsize=1)
def _get_model() -> "BGEM3FlagModel":
    """Load BGE-M3 once (process-wide singleton). Uses CUDA if available, else CPU.

    The model is downloaded on first use if not cached; subsequent loads are
    fully offline. Offline/telemetry mode is configured in ``jantar.__init__``
    at process import time (before any HF library is imported), which is the
    only point where ``HF_HUB_OFFLINE`` is honored by ``huggingface_hub``.
    """
    import logging
    import time

    import torch
    from FlagEmbedding import BGEM3FlagModel

    logger = logging.getLogger(__name__)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    use_fp16 = device == "cuda"
    logger.info("Loading BGE-M3 on %s (fp16=%s)...", device, use_fp16)
    t0 = time.time()
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=use_fp16, device=device)
    logger.info("BGE-M3 loaded in %.1fs", time.time() - t0)
    return model


def warmup_embeddings() -> None:
    """Pre-load the embedding model. Call at app startup to avoid first-query latency."""
    _get_model()


def embed_dense(texts: list[str]) -> list[list[float]]:
    """Produce 1024-dim dense embeddings for queries or passages.

    BGE-M3 does NOT require query/passage prefixes (unlike E5 models).
    The same encode call works for both queries and documents.

    Returns:
        List of 1024-dim float vectors, one per input text.
    """
    if not texts:
        return []
    model = _get_model()
    output = model.encode(
        texts,
        batch_size=_BATCH_SIZE,
        max_length=_MAX_LENGTH,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    return [vec.tolist() for vec in output["dense_vecs"]]


def embed_sparse(texts: list[str]) -> list[dict]:
    """Produce learned sparse vectors (lexical weights) for each text.

    BGE-M3's sparse output is a list of dicts: {token_id: weight}.
    These are learned weights from the model's lexical matching head —
    NOT regex tokenization or TF-IDF approximation.

    Returns:
        List of dicts with 'indices' and 'values' keys, compatible with
        Qdrant's sparse vector format.
    """
    if not texts:
        return []
    model = _get_model()
    output = model.encode(
        texts,
        batch_size=_BATCH_SIZE,
        max_length=_MAX_LENGTH,
        return_dense=False,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    results = []
    for lexical_weights in output["lexical_weights"]:
        # lexical_weights is a dict: {token_id (str): weight (np.float16)}
        # Qdrant requires indices as int and values as float
        indices = [int(k) for k in lexical_weights.keys()]
        values = [float(v) for v in lexical_weights.values()]
        results.append({"indices": indices, "values": values})
    return results


def embed_dense_and_sparse(texts: list[str]) -> tuple[list[list[float]], list[dict]]:
    """Produce BOTH dense and sparse vectors in a single forward pass.

    This is more efficient than calling embed_dense + embed_sparse separately
    because BGE-M3 computes both in one model inference.

    Returns:
        Tuple of (dense_vectors, sparse_vectors).
    """
    if not texts:
        return [], []
    model = _get_model()
    output = model.encode(
        texts,
        batch_size=_BATCH_SIZE,
        max_length=_MAX_LENGTH,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    dense = [vec.tolist() for vec in output["dense_vecs"]]
    sparse = []
    for lexical_weights in output["lexical_weights"]:
        indices = [int(k) for k in lexical_weights.keys()]
        values = [float(v) for v in lexical_weights.values()]
        sparse.append({"indices": indices, "values": values})
    return dense, sparse

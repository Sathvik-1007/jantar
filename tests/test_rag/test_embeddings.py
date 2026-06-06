"""Unit tests for jantar.rag.embeddings — vector format correctness.

The actual model inference is expensive (needs GPU + 4GB model). These tests
verify the FORMAT and TYPE guarantees of the output: sparse vector indices are
int, values are float, dense vectors are lists of floats with correct dimension.

For the full integration test (model + Qdrant), see tests/eval/.
"""

from __future__ import annotations

import pytest


def _gpu_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def test_embed_dense_empty_input():
    """Empty input returns empty output, no model loaded."""
    from jantar.rag.embeddings import embed_dense
    assert embed_dense([]) == []


def test_embed_sparse_empty_input():
    from jantar.rag.embeddings import embed_sparse
    assert embed_sparse([]) == []


def test_embed_dense_and_sparse_empty_input():
    from jantar.rag.embeddings import embed_dense_and_sparse
    dense, sparse = embed_dense_and_sparse([])
    assert dense == []
    assert sparse == []


@pytest.mark.skipif(
    not _gpu_available(),
    reason="No CUDA GPU — skip model-loading tests",
)
class TestWithModel:
    """Tests that require the actual BGE-M3 model loaded on GPU."""

    def test_dense_produces_1024_dim_floats(self):
        from jantar.rag.embeddings import embed_dense
        vecs = embed_dense(["hello world"])
        assert len(vecs) == 1
        assert len(vecs[0]) == 1024
        assert all(isinstance(v, float) for v in vecs[0])

    def test_sparse_indices_are_int_values_are_float(self):
        from jantar.rag.embeddings import embed_sparse
        results = embed_sparse(["hello world"])
        assert len(results) == 1
        sparse = results[0]
        assert "indices" in sparse and "values" in sparse
        assert all(isinstance(i, int) for i in sparse["indices"])
        assert all(isinstance(v, float) for v in sparse["values"])
        assert len(sparse["indices"]) == len(sparse["values"])
        assert len(sparse["indices"]) > 0  # non-empty for real text

    def test_dense_and_sparse_single_pass_matches_individual(self):
        from jantar.rag.embeddings import embed_dense, embed_sparse, embed_dense_and_sparse
        text = ["test query"]
        d1 = embed_dense(text)
        s1 = embed_sparse(text)
        d2, s2 = embed_dense_and_sparse(text)
        # Dense vectors should be identical (same model, same input)
        assert d1[0][:5] == d2[0][:5]  # check first 5 elements
        # Sparse should have same indices (order may vary)
        assert set(s1[0]["indices"]) == set(s2[0]["indices"])

    def test_batch_produces_correct_count(self):
        from jantar.rag.embeddings import embed_dense_and_sparse
        texts = ["one", "two", "three"]
        dense, sparse = embed_dense_and_sparse(texts)
        assert len(dense) == 3
        assert len(sparse) == 3

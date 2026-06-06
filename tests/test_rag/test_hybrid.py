"""Unit tests for Reciprocal Rank Fusion (jantar.rag.hybrid).

RRF is the deterministic fusion step that merges dense and sparse ranked
lists. These tests assert exact scores and ordering, not just "didn't crash".

RRF score for a document = sum over lists of 1 / (k + rank + 1), where rank is
0-indexed. Reference: Cormack et al., "Reciprocal Rank Fusion outperforms
Condorcet and individual Rank Learning Methods" (SIGIR 2009).
"""

from __future__ import annotations

from jantar.rag.hybrid import reciprocal_rank_fusion


def test_empty_input_returns_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_single_list_preserves_order():
    fused = reciprocal_rank_fusion([[("a", 9.0), ("b", 8.0), ("c", 7.0)]])
    assert [doc for doc, _ in fused] == ["a", "b", "c"]


def test_single_list_scores_match_formula():
    k = 60
    fused = dict(reciprocal_rank_fusion([[("a", 9.0), ("b", 8.0)]], k=k))
    assert fused["a"] == 1.0 / (k + 0 + 1)
    assert fused["b"] == 1.0 / (k + 1 + 1)


def test_document_in_both_lists_gets_summed_score():
    k = 60
    dense = [("x", 0.9), ("y", 0.8)]
    sparse = [("y", 0.7), ("x", 0.6)]
    fused = dict(reciprocal_rank_fusion([dense, sparse], k=k))
    # x: rank0 in dense + rank1 in sparse
    assert fused["x"] == 1.0 / (k + 1) + 1.0 / (k + 2)
    # y: rank1 in dense + rank0 in sparse
    assert fused["y"] == 1.0 / (k + 2) + 1.0 / (k + 1)
    # tie -> both equal
    assert fused["x"] == fused["y"]


def test_consensus_doc_outranks_single_list_doc():
    # 'shared' appears (modestly) in both lists; 'only' tops one list only.
    dense = [("only", 1.0), ("shared", 0.5)]
    sparse = [("shared", 0.9)]
    fused = reciprocal_rank_fusion([dense, sparse])
    ranking = [doc for doc, _ in fused]
    assert ranking[0] == "shared"


def test_output_sorted_descending():
    fused = reciprocal_rank_fusion([[("a", 1.0), ("b", 2.0), ("c", 3.0)]])
    scores = [s for _, s in fused]
    assert scores == sorted(scores, reverse=True)


def test_smaller_k_gives_larger_scores():
    high_k = dict(reciprocal_rank_fusion([[("a", 1.0)]], k=60))
    low_k = dict(reciprocal_rank_fusion([[("a", 1.0)]], k=1))
    assert low_k["a"] > high_k["a"]

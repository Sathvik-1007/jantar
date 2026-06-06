from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, float]]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Fuse multiple ranked lists using RRF.

    Each ranked_list is [(doc_id, score), ...] sorted by score desc.
    Returns fused [(doc_id, rrf_score)] sorted desc.
    """
    scores: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, (doc_id, _score) in enumerate(ranked_list):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return fused

"""Golden-set evaluation harness for RAG quality.

Runnable as: pytest tests/eval/test_golden_set.py -v
Requires a live Qdrant with indexed data.
Skipped if QDRANT_URL is unreachable.

This is the minimum viable eval that substantiates quality claims.
It tests retrieval accuracy (does the correct document/tool rank in top-k?)
not answer quality (which requires an LLM judge).
"""

from __future__ import annotations

import pytest

# Golden queries → expected matches. Each entry is:
#   (query, expected_substring_in_top_result_title_or_content, min_score)
KNOWLEDGE_GOLDEN_SET = [
    ("documents required for ration card", "Ration Card", 0.80),
    ("PM-KISAN eligibility criteria", "PM-KISAN", 0.50),
    ("how to apply for Ayushman Bharat", "PM-JAY", 0.50),
    ("documents needed for driving licence", "Driving Licence", 0.80),
    ("passport renewal process", "Passport", 0.50),
    ("DigiLocker supported documents", "DigiLocker", 0.80),
    ("NFSA ration card eligibility BPL", "NFSA", 0.50),
    ("PM-KISAN status check", "PM-KISAN", 0.50),
]

TOOL_GOLDEN_SET = [
    ("wheat price in Delhi mandi", "wheat", 0.01),
    ("weather forecast Mumbai", "mumbai", 0.01),
    ("air quality Delhi PM2.5", "environment", 0.01),
    ("IFSC code SBIN0001234 bank details", "ifsc", 0.01),
    ("pincode 110001 post office", "pincode", 0.01),
]


def _qdrant_reachable():
    """Check if Qdrant is reachable."""
    try:
        from jantar.db import get_qdrant
        client = get_qdrant()
        client.get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _qdrant_reachable(),
    reason="Qdrant unreachable — skip golden-set eval"
)


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_match,min_score", KNOWLEDGE_GOLDEN_SET)
async def test_knowledge_retrieval(query, expected_match, min_score):
    from jantar.rag.knowledge_rag import retrieve_knowledge

    results = await retrieve_knowledge(query, top_k=3)
    assert len(results) > 0, f"No results for: {query}"

    top = results[0]
    title = top["citation"].get("title", "")
    section = top["citation"].get("section", "")
    content = top.get("content", "")
    combined = f"{title} {section} {content}"

    assert expected_match.lower() in combined.lower(), (
        f"Expected '{expected_match}' in top result for '{query}', got title='{title}' section='{section}'"
    )
    assert top["score"] >= min_score, (
        f"Score {top['score']:.4f} < {min_score} for '{query}'"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_match,min_score", TOOL_GOLDEN_SET)
async def test_tool_retrieval(query, expected_match, min_score):
    from jantar.rag.tool_rag import select_tool

    results = await select_tool(query, top_k=1)
    assert len(results) > 0, f"No results for: {query}"

    top = results[0]
    name = top.get("tool_name", "") or top.get("name", "") or top.get("title", "")
    desc = top.get("description", "")
    combined = f"{name} {desc}".lower()

    assert expected_match.lower() in combined, (
        f"Expected '{expected_match}' in top tool for '{query}', got '{name}'"
    )
    assert top["score"] >= min_score, (
        f"Score {top['score']:.4f} < {min_score} for '{query}'"
    )

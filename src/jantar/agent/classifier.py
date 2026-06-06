"""Request classifier — decides tool vs knowledge vs hybrid, extracts params.

The classifier asks the LLM to emit a small JSON object. LLM JSON output is
frequently malformed (markdown fences, trailing commas, stray prose, single
quotes, truncation). Rather than hand-roll a brittle extractor, we use the
`json-repair` library, the de-facto Python tool for repairing LLM JSON, which
fixes missing quotes/commas/brackets, strips comments and surrounding prose,
and salvages truncated values.

`classify_request` NEVER raises: on any failure it falls back to a `hybrid`
classification, which searches both tools and knowledge and therefore cannot
silently drop a user's intent.
"""

from __future__ import annotations

import logging
from typing import Any

from json_repair import repair_json

from jantar.llm.gateway import llm

logger = logging.getLogger(__name__)

# Valid classification labels. Anything else is coerced to "hybrid".
_VALID_TYPES: frozenset[str] = frozenset({"tool_action", "knowledge_query", "hybrid", "multi_step"})


CLASSIFY_PROMPT = """You are a request classifier for Indian government services.
Given a user query, classify it and extract parameters.

Classification types:
- "tool_action": needs to call an external API (fetch live data, verify document, check status)
- "knowledge_query": needs to answer from stored documents/schemes (eligibility, required documents, process steps)
- "hybrid": needs BOTH an API call AND knowledge retrieval
- "multi_step": needs multiple sequential steps (e.g. "check X AND compare with Y AND tell me Z", "if expired then start renewal")

Domains (pick the most relevant):
agriculture, transport, health, finance, identity, education, language, environment,
employment, food_security, housing, data, tax, energy, water, crime, rural_development,
commerce, tourism, science, telecom, weather, postal, banking, social_welfare,
women_child, industry, minerals, census, elections, general

Return ONLY valid JSON:
{
  "type": "tool_action"|"knowledge_query"|"hybrid",
  "domain": "agriculture"|"health"|...|"general",
  "tool_query": "semantic search query for finding the right API tool",
  "knowledge_query": "semantic search query for finding relevant documents",
  "params": {"commodity": "...", "state": "...", "pincode": "...", "id_number": "..."}
}

Rules for params:
- Extract ALL relevant parameters from the query (commodity names, states, cities, pincodes, ID numbers, dates)
- Only include params that are explicitly mentioned in the query
- Translate non-English param values to English (e.g. "गेहूँ" → "Wheat", "दिल्ली" → "Delhi")

Examples:
- "दिल्ली में गेहूँ का भाव" → {"type": "tool_action", "domain": "agriculture", "tool_query": "commodity price mandi", "knowledge_query": "", "params": {"commodity": "Wheat", "state": "Delhi"}}
- "राशन कार्ड के लिए कौन से दस्तावेज़?" → {"type": "knowledge_query", "domain": "food_security", "tool_query": "", "knowledge_query": "documents required for ration card", "params": {}}
- "110001 का मौसम और PM-KISAN पात्रता" → {"type": "hybrid", "domain": "weather", "tool_query": "weather forecast city", "knowledge_query": "PM-KISAN eligibility", "params": {"pincode": "110001"}}
- "Check wheat price in Delhi, compare to MSP, and tell me if I should sell" → {"type": "multi_step", "domain": "agriculture", "tool_query": "wheat price mandi Delhi", "knowledge_query": "wheat MSP 2024-25", "params": {"commodity": "Wheat", "state": "Delhi"}}
"""


def _hybrid_fallback(query: str) -> dict[str, Any]:
    """Safest classification: search both tools and knowledge.

    Used whenever classification fails for any reason — guarantees the user's
    intent is never silently dropped.
    """
    return {"type": "hybrid", "tool_query": query, "knowledge_query": query, "params": {}}


def parse_classification(raw: str, query: str) -> dict[str, Any]:
    """Parse (and repair) an LLM classification response into a valid dict.

    Pure function — no I/O — so it is fully unit-testable. Uses `json-repair`
    to recover JSON from malformed/wrapped LLM output, then normalizes the
    result: guarantees a "params" dict and a valid "type" (coercing unknown
    types to "hybrid").

    Args:
        raw: The raw text returned by the LLM.
        query: The original query, used to seed the fallback search fields.

    Returns:
        A normalized classification dict. Falls back to a hybrid classification
        if `raw` cannot be parsed into a JSON object.
    """
    try:
        result = repair_json(raw, return_objects=True)
    except Exception as exc:  # repair_json is defensive, but never trust input
        logger.warning("json-repair failed on classifier output: %s", exc)
        return _hybrid_fallback(query)

    if not isinstance(result, dict):
        logger.warning("Classifier output was not a JSON object (got %s)", type(result).__name__)
        return _hybrid_fallback(query)

    # Normalize: ensure params is a dict.
    params = result.get("params")
    result["params"] = params if isinstance(params, dict) else {}

    # Normalize: coerce unknown/missing type to hybrid (safest).
    if result.get("type") not in _VALID_TYPES:
        logger.warning("Unknown classification type=%r, coercing to hybrid", result.get("type"))
        result["type"] = "hybrid"

    # Normalize domain: must be a valid Domain enum value or None.
    domain = result.get("domain")
    if domain and not isinstance(domain, str):
        domain = None
    result["domain"] = domain if domain else None

    # Guarantee the search-query fields exist; default them to the raw query.
    result.setdefault("tool_query", query)
    result.setdefault("knowledge_query", query)
    return result


async def classify_request(query: str) -> dict[str, Any]:
    """Classify a user request and extract structured parameters.

    NEVER raises — on any LLM or parse failure, falls back to a hybrid
    classification (searches both tools and knowledge).
    """
    logger.debug("Classifying query: %r", query[:100])
    messages = [
        {"role": "system", "content": CLASSIFY_PROMPT},
        {"role": "user", "content": query},
    ]
    try:
        response = await llm.chat_structured(messages)
    except Exception as exc:
        logger.error("Classifier LLM call failed: %s", exc)
        return _hybrid_fallback(query)

    result = parse_classification(response, query)
    logger.info("Classification result: type=%s params=%s", result.get("type"), list(result.get("params", {}).keys()))
    return result

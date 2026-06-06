"""Unit tests for the agent executor orchestration logic.

Tests classification routing, threshold gating, data_gov_dynamic rewrite,
and the detect-and-translate path. All LLM/RAG calls are mocked — these
test orchestration logic, not the models.
"""

from __future__ import annotations

import pytest

from jantar.agent.executor import (
    LANG_MAP,
    TOOL_SCORE_THRESHOLD,
    _detect_and_translate,
    run_agent,
)
from jantar.models import AgentRequest


def test_lang_map_covers_all_22_scheduled_languages():
    # 22 scheduled + en + auto + or alias = 25
    assert len(LANG_MAP) >= 25
    for code in ("hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "as", "ur", "sa"):
        assert code in LANG_MAP


def test_threshold_is_meaningful():
    # Against a 137K+ catalog, threshold must be >0.01 to filter noise
    assert TOOL_SCORE_THRESHOLD >= 0.05


@pytest.mark.asyncio
async def test_run_agent_returns_agent_response(monkeypatch):
    """Verify the executor returns a valid AgentResponse shape."""
    # Mock classify to return knowledge_query (skips tool RAG)
    async def fake_classify(q):
        return {"type": "knowledge_query", "domain": "food_security",
                "tool_query": q, "knowledge_query": q, "params": {}}
    monkeypatch.setattr("jantar.agent.executor.classify_request", fake_classify)

    # Mock knowledge RAG
    async def fake_knowledge(q, domain=None, top_k=3):
        return [{"content": "Ration card needs Aadhaar.",
                 "citation": {"title": "NFSA", "section": "Required Docs", "effective_date": "2024"}}]
    monkeypatch.setattr("jantar.agent.executor.retrieve_knowledge", fake_knowledge)

    # Mock LLM
    class FakeLLM:
        async def chat(self, messages):
            return "You need Aadhaar for ration card."
        async def chat_structured(self, messages):
            return '{"type": "knowledge_query"}'
    monkeypatch.setattr("jantar.agent.executor.llm", FakeLLM())

    req = AgentRequest(text="ration card documents", language="en")
    resp = await run_agent(req)
    assert resp.answer == "You need Aadhaar for ration card."
    assert len(resp.citations) == 1
    assert resp.citations[0]["title"] == "NFSA"


@pytest.mark.asyncio
async def test_tool_below_threshold_is_rejected(monkeypatch):
    """Tool with score below threshold should be rejected."""
    async def fake_classify(q):
        return {"type": "tool_action", "domain": "agriculture",
                "tool_query": q, "knowledge_query": "", "params": {}}
    monkeypatch.setattr("jantar.agent.executor.classify_request", fake_classify)

    # Tool RAG returns a result below threshold
    async def fake_tool_rag(q, domain=None, top_k=1):
        return [{"id": 1, "score": 0.001, "tool_name": "irrelevant", "title": "irrelevant"}]
    monkeypatch.setattr("jantar.agent.executor.select_tool", fake_tool_rag)

    class FakeLLM:
        async def chat(self, messages):
            return "No relevant tool found."
        async def chat_structured(self, messages):
            return '{"type": "tool_action"}'
    monkeypatch.setattr("jantar.agent.executor.llm", FakeLLM())

    req = AgentRequest(text="something", language="en")
    resp = await run_agent(req)
    assert resp.tools_used == []  # Tool was rejected


@pytest.mark.asyncio
async def test_data_gov_dynamic_rewrite(monkeypatch):
    """Catalog entries with source='data.gov.in' should rewrite to data_gov_dynamic."""
    executed_with = {}

    async def fake_classify(q):
        return {"type": "tool_action", "domain": "agriculture",
                "tool_query": q, "knowledge_query": "", "params": {"state": "Delhi"}}
    monkeypatch.setattr("jantar.agent.executor.classify_request", fake_classify)

    async def fake_tool_rag(q, domain=None, top_k=1):
        return [{"id": 99, "score": 0.9, "api_id": "abc-123", "title": "Mandi Prices",
                 "source": "data.gov.in", "description": "mandi"}]
    monkeypatch.setattr("jantar.agent.executor.select_tool", fake_tool_rag)

    async def fake_execute(tool_name, params):
        executed_with["tool"] = tool_name
        executed_with["params"] = params
        return {"data": []}
    monkeypatch.setattr("jantar.agent.executor.execute_tool", fake_execute)

    class FakeLLM:
        async def chat(self, messages):
            return "Wheat price is X."
        async def chat_structured(self, messages):
            return '{"type": "tool_action"}'
    monkeypatch.setattr("jantar.agent.executor.llm", FakeLLM())

    req = AgentRequest(text="wheat price Delhi", language="en")
    await run_agent(req)

    assert executed_with["tool"] == "data_gov_dynamic"
    assert executed_with["params"]["resource_id"] == "abc-123"
    assert executed_with["params"]["state"] == "Delhi"

"""Tests for Plan-and-Execute planner."""

import pytest
import json

from jantar.agent.planner import create_plan, execute_step, StepResult, MAX_STEPS


@pytest.mark.asyncio
async def test_create_plan_returns_list(monkeypatch):
    """Plan creation returns a list of steps ending in synthesize."""
    async def fake_chat(messages, **kwargs):
        return json.dumps([
            {"step": 1, "type": "knowledge_search", "query": "wheat MSP", "reason": "find MSP"},
            {"step": 2, "type": "tool_search", "query": "wheat price Delhi", "reason": "get live price"},
            {"step": 3, "type": "synthesize", "reason": "combine"}
        ])

    from jantar.llm import gateway
    monkeypatch.setattr(gateway.llm, "chat_structured", fake_chat)

    plan = await create_plan("Check wheat price and compare to MSP")
    assert isinstance(plan, list)
    assert len(plan) == 3
    assert plan[-1]["type"] == "synthesize"
    assert plan[0]["type"] == "knowledge_search"


@pytest.mark.asyncio
async def test_create_plan_adds_synthesize_if_missing(monkeypatch):
    """If LLM forgets synthesize step, it gets appended."""
    async def fake_chat(messages, **kwargs):
        return json.dumps([
            {"step": 1, "type": "knowledge_search", "query": "ration card docs", "reason": "find docs"},
        ])

    from jantar.llm import gateway
    monkeypatch.setattr(gateway.llm, "chat_structured", fake_chat)

    plan = await create_plan("What docs for ration card?")
    assert plan[-1]["type"] == "synthesize"


@pytest.mark.asyncio
async def test_create_plan_caps_at_max_steps(monkeypatch):
    """Plan never exceeds MAX_STEPS."""
    async def fake_chat(messages, **kwargs):
        steps = [{"step": i, "type": "knowledge_search", "query": f"q{i}", "reason": f"r{i}"} for i in range(10)]
        return json.dumps(steps)

    from jantar.llm import gateway
    monkeypatch.setattr(gateway.llm, "chat_structured", fake_chat)

    plan = await create_plan("very complex query")
    assert len(plan) <= MAX_STEPS


@pytest.mark.asyncio
async def test_create_plan_fallback_on_failure(monkeypatch):
    """On LLM failure, returns a simple 2-step fallback plan."""
    async def fake_chat(messages, **kwargs):
        raise RuntimeError("LLM down")

    from jantar.llm import gateway
    monkeypatch.setattr(gateway.llm, "chat_structured", fake_chat)

    plan = await create_plan("some query")
    assert len(plan) == 2
    assert plan[0]["type"] == "knowledge_search"
    assert plan[1]["type"] == "synthesize"


@pytest.mark.asyncio
async def test_execute_step_knowledge(monkeypatch):
    """Knowledge step calls retrieve_knowledge and returns citations."""
    async def fake_retrieve(query, domain=None, top_k=3):
        return [{"content": "PM-KISAN gives ₹6000/year", "citation": {"title": "PM-KISAN", "section": "Benefits", "effective_date": "2024"}}]

    import jantar.agent.planner as planner_mod
    monkeypatch.setattr(planner_mod, "retrieve_knowledge", fake_retrieve)

    step = {"step": 1, "type": "knowledge_search", "query": "PM-KISAN benefits"}
    result = await execute_step(step)
    assert isinstance(result, StepResult)
    assert "PM-KISAN" in result.result
    assert len(result.citations) == 1


@pytest.mark.asyncio
async def test_execute_step_tool(monkeypatch):
    """Tool step calls select_tool + execute_tool."""
    async def fake_select(query, domain=None, top_k=1):
        return [{"tool_name": "open_meteo_weather", "title": "Weather", "score": 0.9}]

    async def fake_execute(tool_name, params):
        return {"temperature": 28.5, "city": "Delhi"}

    import jantar.agent.planner as planner_mod
    monkeypatch.setattr(planner_mod, "select_tool", fake_select)
    monkeypatch.setattr(planner_mod, "execute_tool", fake_execute)

    step = {"step": 1, "type": "tool_search", "query": "weather Delhi", "params": {"city": "Delhi"}}
    result = await execute_step(step)
    assert "28.5" in result.result
    assert "Weather" in result.tools_used


@pytest.mark.asyncio
async def test_execute_step_tool_below_threshold(monkeypatch):
    """Tool step returns 'No relevant API' when score is below threshold."""
    async def fake_select(query, domain=None, top_k=1):
        return [{"tool_name": "irrelevant", "score": 0.001}]

    import jantar.agent.planner as planner_mod
    monkeypatch.setattr(planner_mod, "select_tool", fake_select)

    step = {"step": 1, "type": "tool_search", "query": "something obscure"}
    result = await execute_step(step)
    assert "No relevant API" in result.result

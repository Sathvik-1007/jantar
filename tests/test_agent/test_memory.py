"""Tests for ConversationMemory — progressive summary buffer."""

import pytest

from jantar.agent.memory import ConversationMemory, Turn, MAX_BUFFER


def test_empty_memory_returns_empty_context():
    mem = ConversationMemory()
    assert mem.get_context() == ""
    assert mem.is_empty()


def test_add_turn_makes_non_empty():
    mem = ConversationMemory()
    mem.add("hello", "world")
    assert not mem.is_empty()
    assert len(mem.buffer) == 1


def test_buffer_grows():
    mem = ConversationMemory()
    for i in range(3):
        mem.add(f"q{i}", f"a{i}")
    assert len(mem.buffer) == 3


def test_needs_summarization_false_within_limit():
    mem = ConversationMemory()
    for i in range(MAX_BUFFER):
        mem.add(f"q{i}", f"a{i}")
    assert not mem.needs_summarization()


def test_needs_summarization_true_over_limit():
    mem = ConversationMemory()
    for i in range(MAX_BUFFER + 1):
        mem.add(f"q{i}", f"a{i}")
    assert mem.needs_summarization()


def test_get_context_includes_recent():
    mem = ConversationMemory()
    mem.add("What is PM-KISAN?", "PM-KISAN provides ₹6000/year to farmers")
    ctx = mem.get_context()
    assert "PM-KISAN" in ctx
    assert "User:" in ctx


def test_get_context_includes_summary():
    mem = ConversationMemory()
    mem.summary = "User asked about ration card documents."
    mem.add("What about Tamil Nadu?", "In TN, apply via...")
    ctx = mem.get_context()
    assert "Conversation summary:" in ctx
    assert "ration card" in ctx
    assert "Tamil Nadu" in ctx


@pytest.mark.asyncio
async def test_maybe_summarize_no_op_within_limit():
    mem = ConversationMemory()
    mem.add("q1", "a1")
    mem.add("q2", "a2")
    await mem.maybe_summarize()
    assert mem.summary == ""
    assert len(mem.buffer) == 2


@pytest.mark.asyncio
async def test_maybe_summarize_compresses_overflow(monkeypatch):
    """When buffer overflows, oldest 2 turns get summarized."""
    mem = ConversationMemory()
    for i in range(MAX_BUFFER + 1):
        mem.add(f"question {i}", f"answer {i}")

    # Mock the LLM call
    async def fake_chat(messages, **kwargs):
        return "Summary: discussed questions 0 and 1"

    from jantar.llm import gateway
    monkeypatch.setattr(gateway.llm, "chat", fake_chat)

    await mem.maybe_summarize()
    assert "discussed questions 0 and 1" in mem.summary
    assert len(mem.buffer) == MAX_BUFFER - 1  # 5 - 2 = 3

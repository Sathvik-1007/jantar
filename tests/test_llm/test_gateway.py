"""Unit tests for jantar.llm.gateway.

Tests the pure `extract_message_content` helper exhaustively (all edge cases of
Sarvam's response format) and verifies retry + error behavior of `LLMGateway.chat`
via fake HTTP responses.
"""

from __future__ import annotations

import pytest

from jantar.llm.gateway import LLMGateway, extract_message_content
from helpers import FakeResponse, install_fake_httpx
import jantar.llm.gateway as gw_mod


# --- extract_message_content: pure function tests (no I/O) ---


def test_standard_response_extracts_content():
    data = {"choices": [{"message": {"content": "hello", "reasoning_content": None}}]}
    assert extract_message_content(data) == "hello"


def test_reasoning_model_response_uses_reasoning_content():
    """Sarvam-30b puts answer in reasoning_content, content=null."""
    data = {"choices": [{"message": {"content": None, "reasoning_content": "answer here"}}]}
    assert extract_message_content(data) == "answer here"


def test_content_preferred_over_reasoning():
    data = {"choices": [{"message": {"content": "real", "reasoning_content": "thinking"}}]}
    assert extract_message_content(data) == "real"


def test_empty_content_falls_to_reasoning():
    data = {"choices": [{"message": {"content": "", "reasoning_content": "fallback"}}]}
    assert extract_message_content(data) == "fallback"


def test_empty_choices_returns_empty():
    assert extract_message_content({"choices": []}) == ""


def test_missing_choices_key_returns_empty():
    assert extract_message_content({}) == ""


def test_missing_message_key_returns_empty():
    assert extract_message_content({"choices": [{}]}) == ""


def test_null_message_returns_empty():
    assert extract_message_content({"choices": [{"message": None}]}) == ""


def test_no_content_or_reasoning_returns_empty():
    data = {"choices": [{"message": {"role": "assistant"}}]}
    assert extract_message_content(data) == ""


# --- LLMGateway.chat: network behavior tests ---


@pytest.mark.asyncio
async def test_chat_raises_on_empty_api_key(monkeypatch):
    """Must fail fast with clear error, not send malformed header."""
    monkeypatch.setattr(gw_mod.settings, "sarvam_api_key", "")
    gateway = LLMGateway()
    gateway.api_key = ""  # simulate empty key
    with pytest.raises(RuntimeError, match="SARVAM_API_KEY is not set"):
        await gateway.chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_success(monkeypatch):
    resp_body = {"choices": [{"message": {"content": "world"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}}
    install_fake_httpx(monkeypatch, gw_mod, [FakeResponse(200, resp_body)])
    gateway = LLMGateway()
    gateway.api_key = "sk_test"
    result = await gateway.chat([{"role": "user", "content": "hello"}])
    assert result == "world"


@pytest.mark.asyncio
async def test_chat_retries_on_429(monkeypatch):
    """Retries on 429, succeeds on third attempt."""
    monkeypatch.setattr(gw_mod, "_RETRY_BACKOFF", [0, 0, 0])  # no delay in tests
    good = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
    install_fake_httpx(monkeypatch, gw_mod, [
        FakeResponse(429, {}),
        FakeResponse(429, {}),
        FakeResponse(200, good),
    ])
    gateway = LLMGateway()
    gateway.api_key = "sk_test"
    result = await gateway.chat([{"role": "user", "content": "hi"}])
    assert result == "ok"


@pytest.mark.asyncio
async def test_chat_non_retryable_error_raises(monkeypatch):
    monkeypatch.setattr(gw_mod, "_RETRY_BACKOFF", [0, 0, 0])
    install_fake_httpx(monkeypatch, gw_mod, [FakeResponse(400, {}, text="Bad request")])
    gateway = LLMGateway()
    gateway.api_key = "sk_test"
    with pytest.raises(Exception):  # HTTPStatusError
        await gateway.chat([{"role": "user", "content": "hi"}])

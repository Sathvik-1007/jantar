"""Unit tests for the Sarvam adapter (jantar.tools.adapters.sarvam).

Verifies translate model selection (auto -> mayura:v1, explicit ->
sarvam-translate:v1), execute() routing, and that no real network call is made
(httpx is faked).
"""

from __future__ import annotations

import pytest

import jantar.tools.adapters.sarvam as sarvam_mod
from helpers import FakeResponse, install_fake_httpx

ADAPTER = sarvam_mod.sarvam


def test_handles_lists_expected_tools():
    assert set(ADAPTER.handles()) == {"sarvam_translate", "sarvam_stt"}


@pytest.mark.asyncio
async def test_translate_auto_uses_mayura_model(monkeypatch):
    fake = install_fake_httpx(
        monkeypatch, sarvam_mod, [FakeResponse(200, {"translated_text": "hello"})]
    )
    out = await ADAPTER.translate("नमस्ते", "auto", "en-IN")
    assert out == "hello"
    assert fake.calls[0]["json"]["model"] == "mayura:v1"
    assert fake.calls[0]["json"]["source_language_code"] == "auto"


@pytest.mark.asyncio
async def test_translate_explicit_uses_sarvam_translate_model(monkeypatch):
    fake = install_fake_httpx(
        monkeypatch, sarvam_mod, [FakeResponse(200, {"translated_text": "வணக்கம்"})]
    )
    out = await ADAPTER.translate("hello", "en-IN", "ta-IN")
    assert out == "வணக்கம்"
    assert fake.calls[0]["json"]["model"] == "sarvam-translate:v1"


@pytest.mark.asyncio
async def test_execute_routes_to_translate(monkeypatch):
    install_fake_httpx(monkeypatch, sarvam_mod, [FakeResponse(200, {"translated_text": "x"})])
    out = await ADAPTER.execute("sarvam_translate", {"text": "hi", "source_lang": "auto"})
    assert out == "x"


@pytest.mark.asyncio
async def test_execute_unknown_tool_returns_error_dict():
    out = await ADAPTER.execute("sarvam_unknown", {})
    assert "error" in out


@pytest.mark.asyncio
async def test_translate_uses_subscription_key_header(monkeypatch):
    fake = install_fake_httpx(
        monkeypatch, sarvam_mod, [FakeResponse(200, {"translated_text": "ok"})]
    )
    await ADAPTER.translate("hi", "auto", "en-IN")
    # Sarvam non-chat APIs authenticate via api-subscription-key, not Bearer.
    assert "api-subscription-key" in fake.calls[0]["headers"]

"""Test doubles for httpx — simulate the Sarvam HTTP API without network.

These fakes mirror the small slice of the httpx async API that Jantar uses:
``AsyncClient`` as an async context manager exposing ``post``, returning a
response object with ``status_code``, ``json()``, ``text`` and
``raise_for_status()``.

Not collected by pytest (no ``test_`` prefix).
"""

from __future__ import annotations

from typing import Any

import httpx


class FakeResponse:
    """Minimal stand-in for ``httpx.Response``."""

    def __init__(self, status_code: int = 200, json_body: dict[str, Any] | None = None, text: str = ""):
        self.status_code = status_code
        self._json = json_body if json_body is not None else {}
        self.text = text or str(self._json)

    def json(self) -> dict[str, Any]:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.sarvam.ai/test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=request, response=response
            )


class FakeAsyncClient:
    """Async-context-manager fake for ``httpx.AsyncClient``.

    Returns queued responses in order on each ``post`` call. Records every
    request's kwargs in ``calls`` for assertions (e.g. checking the model name
    in the JSON body).
    """

    # Class-level shared state so a monkeypatched constructor can reach it.
    responses: list[FakeResponse] = []
    calls: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any):
        self.init_kwargs = kwargs

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        FakeAsyncClient.calls.append({"url": url, **kwargs})
        if not FakeAsyncClient.responses:
            raise AssertionError("FakeAsyncClient.post called with no queued responses")
        return FakeAsyncClient.responses.pop(0)


def install_fake_httpx(monkeypatch, module, responses: list[FakeResponse]) -> type[FakeAsyncClient]:
    """Patch ``module.httpx.AsyncClient`` with a fresh FakeAsyncClient.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        module: the imported module whose ``httpx`` reference to patch.
        responses: queued responses returned by successive ``post`` calls.

    Returns:
        The FakeAsyncClient class (with reset ``calls``) for assertions.
    """
    FakeAsyncClient.responses = list(responses)
    FakeAsyncClient.calls = []
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient

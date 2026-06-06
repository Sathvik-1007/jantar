from __future__ import annotations

import asyncio
import logging
import time

import httpx

from jantar.config import settings

logger = logging.getLogger(__name__)

# Retryable HTTP status codes
_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1, 3, 8]  # seconds


def extract_message_content(data: dict) -> str:
    """Extract the assistant message text from a chat-completions response.

    Sarvam's reasoning models place the final answer in either ``content`` or,
    for reasoning traces, ``reasoning_content``. This helper handles both and
    degrades gracefully (returns "") on a malformed/empty response rather than
    raising a KeyError/IndexError.

    Args:
        data: Parsed JSON body of the chat-completions response.

    Returns:
        The message text, or "" if no usable content is present.
    """
    choices = data.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {}) or {}
    return message.get("content") or message.get("reasoning_content") or ""


class LLMGateway:
    """Unified LLM interface — wraps Sarvam's OpenAI-compatible endpoint."""

    def __init__(self):
        self.base_url = "https://api.sarvam.ai/v1"
        self.api_key = settings.sarvam_api_key.strip()

    async def chat(
        self,
        messages: list[dict],
        model: str = "sarvam-30b",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Send chat completion request to Sarvam AI with retries.

        Raises:
            RuntimeError: if no Sarvam API key is configured. Failing here with
                a clear message avoids the opaque ``Illegal header value``
                error httpx raises when an empty ``Bearer`` header is sent.
        """
        if not self.api_key:
            raise RuntimeError(
                "SARVAM_API_KEY is not set. Add it to the .env file at the "
                "project root (SARVAM_API_KEY=sk_...). See .env.example."
            )

        t0 = time.perf_counter()
        logger.info("LLM request | model=%s temp=%.1f max_tokens=%d", model, temperature, max_tokens)

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=180) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                    )

                elapsed = time.perf_counter() - t0
                if resp.status_code in _RETRYABLE:
                    logger.warning("LLM retryable error | status=%d attempt=%d/%d", resp.status_code, attempt + 1, _MAX_RETRIES)
                    if attempt < _MAX_RETRIES - 1:
                        await asyncio.sleep(_RETRY_BACKOFF[attempt])
                        continue
                    resp.raise_for_status()

                if resp.status_code != 200:
                    logger.error("LLM error | status=%d elapsed=%.2fs body=%s", resp.status_code, elapsed, resp.text[:200])
                    resp.raise_for_status()

                data = resp.json()
                usage = data.get("usage", {})
                logger.info(
                    "LLM response | elapsed=%.2fs prompt_tokens=%d completion_tokens=%d total_tokens=%d",
                    elapsed, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), usage.get("total_tokens", 0),
                )
                content = extract_message_content(data)
                if not content:
                    logger.error("LLM returned no usable content | data_keys=%s", list(data.keys()))
                return content

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning("LLM timeout | attempt=%d/%d elapsed=%.2fs", attempt + 1, _MAX_RETRIES, time.perf_counter() - t0)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_RETRY_BACKOFF[attempt])
                    continue
            except httpx.HTTPStatusError as e:
                last_error = e
                break  # Non-retryable HTTP error
            except Exception as e:
                last_error = e
                logger.error("LLM unexpected error: %s", e, exc_info=True)
                break

        raise last_error or RuntimeError("LLM request failed after retries")

    async def chat_structured(
        self,
        messages: list[dict],
        model: str = "sarvam-30b",
        temperature: float = 0.0,
    ) -> str:
        """Chat with low temperature for structured/classification tasks."""
        return await self.chat(messages, model=model, temperature=temperature)


llm = LLMGateway()

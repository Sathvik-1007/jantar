from __future__ import annotations

from typing import Any

import httpx

from jantar.config import settings
from jantar.tools.base import ToolAdapter


class SarvamAdapter(ToolAdapter):
    """Adapter for Sarvam AI non-chat APIs: translate, STT, TTS."""

    def __init__(self):
        self.base_url = settings.sarvam_base_url
        self.headers = {"api-subscription-key": settings.sarvam_api_key}

    def handles(self) -> list[str]:
        return ["sarvam_translate", "sarvam_stt"]

    async def execute(self, tool_name: str, params: dict[str, Any]) -> Any:
        if tool_name == "sarvam_translate":
            return await self.translate(
                params.get("text", ""),
                params.get("source_lang", "auto"),
                params.get("target_lang", "en-IN"),
            )
        elif tool_name == "sarvam_stt":
            return await self.speech_to_text(params.get("audio", ""), params.get("language", "hi-IN"))
        return {"error": f"Unknown Sarvam tool: {tool_name}"}

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text. Uses mayura:v1 for auto-detect, sarvam-translate:v1 for explicit (23 langs)."""
        model = "mayura:v1" if source_lang == "auto" else "sarvam-translate:v1"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/translate",
                headers=self.headers,
                json={
                    "input": text,
                    "source_language_code": source_lang,
                    "target_language_code": target_lang,
                    "model": model,
                    "enable_preprocessing": True,
                },
            )
            resp.raise_for_status()
            return resp.json()["translated_text"]

    async def speech_to_text(self, audio_base64: str, language: str = "unknown") -> str:
        """Transcribe audio. Supports 23 languages via saaras:v3.
        Pass language='unknown' for auto-detection."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/speech-to-text",
                headers=self.headers,
                json={
                    "input": audio_base64,
                    "language_code": language,
                    "model": "saaras:v3",
                    "with_timestamps": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["transcript"]

    async def text_to_speech(self, text: str, language: str = "hi-IN", speaker: str = "meera") -> str:
        """Generate speech audio (base64). Supports 11 languages via bulbul:v3."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/text-to-speech",
                headers=self.headers,
                json={
                    "inputs": [text],
                    "target_language_code": language,
                    "model": "bulbul:v3",
                    "speaker": speaker,
                    "enable_preprocessing": True,
                },
            )
            resp.raise_for_status()
            return resp.json()["audios"][0]


sarvam = SarvamAdapter()

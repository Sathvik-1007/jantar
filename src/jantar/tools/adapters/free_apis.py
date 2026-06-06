from __future__ import annotations

import logging
from typing import Any

import httpx

from jantar.tools.base import ToolAdapter

logger = logging.getLogger(__name__)


class FreeApisAdapter(ToolAdapter):
    """Adapter for free, no-auth government/public-infra APIs."""

    def handles(self) -> list[str]:
        return [
            "india_post_pincode",
            "razorpay_ifsc",
        ]

    async def execute(self, tool_name: str, params: dict[str, Any]) -> Any:
        if tool_name == "india_post_pincode":
            return await self._india_post(params)
        elif tool_name == "razorpay_ifsc":
            return await self._razorpay_ifsc(params)
        return {"error": f"Unknown tool: {tool_name}"}

    async def _india_post(self, params: dict[str, Any]) -> Any:
        pincode = params.get("pincode")
        postoffice_name = params.get("postoffice_name")

        if pincode:
            url = f"https://api.postalpincode.in/pincode/{pincode}"
        elif postoffice_name:
            url = f"https://api.postalpincode.in/postoffice/{postoffice_name}"
        else:
            return {"error": "Provide either pincode or postoffice_name"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            data = resp.json()
            if data and data[0].get("Status") == "Success":
                return data[0].get("PostOffice", [])
            return {"error": data[0].get("Message", "Not found") if data else "No response"}

    async def _razorpay_ifsc(self, params: dict[str, Any]) -> Any:
        ifsc = params.get("ifsc", "").strip().upper()
        if not ifsc or len(ifsc) != 11:
            return {"error": "Provide a valid 11-character IFSC code"}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://ifsc.razorpay.com/{ifsc}")
            if resp.status_code == 404:
                return {"error": f"IFSC code {ifsc} not found"}
            resp.raise_for_status()
            return resp.json()


free_apis = FreeApisAdapter()

"""data.gov.in adapter — queries ANY of the 270,000+ government datasets.

The catalog ingest indexes 5,500+ APIs into Qdrant. When RAG selects one,
the executor passes the resource_id (api_id from catalog) to this adapter.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from jantar.config import settings
from jantar.tools.base import ToolAdapter

logger = logging.getLogger(__name__)


class DataGovAdapter(ToolAdapter):
    """Queries any data.gov.in dataset by resource_id."""

    BASE_URL = "https://api.data.gov.in/resource"

    def handles(self) -> list[str]:
        return ["data_gov_dynamic"]

    async def execute(self, tool_name: str, params: dict[str, Any]) -> Any:
        if not settings.data_gov_api_key:
            return {
                "error": "data.gov.in API key not configured",
                "action": "Register free at https://data.gov.in and add DATA_GOV_API_KEY to .env",
            }

        resource_id = params.pop("resource_id", None)
        if not resource_id:
            return {"error": "No resource_id provided"}

        request_params: dict[str, Any] = {
            "api-key": settings.data_gov_api_key,
            "format": "json",
            "limit": params.pop("limit", 10),
        }
        # Remaining params become filters
        for k, v in params.items():
            if v:
                request_params[f"filters[{k}]"] = v

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{self.BASE_URL}/{resource_id}", params=request_params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("records", [])


data_gov = DataGovAdapter()

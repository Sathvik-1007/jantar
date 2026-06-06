"""Adapter registry — maps tool names to their adapter instances.

Replaces if/elif dispatch chains. Adding a new adapter is: implement ToolAdapter,
instantiate it, import it here. The registry builds itself from handles().
"""

from __future__ import annotations

import logging
import time
from typing import Any

from jantar.tools.base import ToolAdapter
from jantar.tools.adapters.data_gov import data_gov
from jantar.tools.adapters.sarvam import sarvam as sarvam_adapter
from jantar.tools.adapters.open_meteo import open_meteo
from jantar.tools.adapters.free_apis import free_apis

logger = logging.getLogger(__name__)

# All registered adapter instances — government services + citizen utilities only
_ADAPTERS: list[ToolAdapter] = [data_gov, sarvam_adapter, open_meteo, free_apis]

# Build dispatch map: tool_name → adapter
_DISPATCH: dict[str, ToolAdapter] = {}
for adapter in _ADAPTERS:
    for name in adapter.handles():
        _DISPATCH[name] = adapter


async def execute_tool(tool_name: str, params: dict[str, Any]) -> Any:
    """Execute a tool by name using the appropriate adapter.

    NEVER raises — returns error dict on any failure (network, timeout, etc.)
    """
    adapter = _DISPATCH.get(tool_name)
    if not adapter:
        logger.warning("No adapter for tool=%s — returning no_live_adapter stub", tool_name)
        return {"status": "no_live_adapter", "tool": tool_name, "params": params}

    t0 = time.perf_counter()
    logger.info("Executing tool=%s adapter=%s params=%s", tool_name, type(adapter).__name__, list(params.keys()))
    try:
        result = await adapter.execute(tool_name, params)
        logger.info("Tool complete=%s elapsed=%.2fs", tool_name, time.perf_counter() - t0)
        return result
    except Exception as e:
        logger.error("Tool failed=%s error=%s elapsed=%.2fs", tool_name, e, time.perf_counter() - t0, exc_info=True)
        return {"status": "error", "tool": tool_name, "error": str(e)}

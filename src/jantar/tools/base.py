"""Base adapter interface — all tool adapters implement this contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolAdapter(ABC):
    """Contract for tool execution adapters.

    Each adapter handles one or more tool names and knows how to execute
    them given LLM-extracted params.
    """

    @abstractmethod
    async def execute(self, tool_name: str, params: dict[str, Any]) -> Any:
        """Execute the named tool with given params. Returns structured data."""
        ...

    @abstractmethod
    def handles(self) -> list[str]:
        """Return list of tool names this adapter can execute."""
        ...

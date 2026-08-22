from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    handler: Callable[..., Any]
    description: str = ""
    agents: frozenset[str] | None = None


class ToolRegistry:
    """Thread-safe runtime registry used to scope tools to an agent."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {}
        self._lock = RLock()

    def register(self, name: str, handler: Callable[..., Any], description: str = "", agents: Iterable[str] | None = None, replace: bool = False) -> ToolRegistration:
        if not name or not callable(handler):
            raise ValueError("A non-empty tool name and callable handler are required")
        item = ToolRegistration(name, handler, description, frozenset(agents) if agents else None)
        with self._lock:
            if name in self._tools and not replace:
                raise ValueError(f"Tool '{name}' is already registered")
            self._tools[name] = item
        return item

    def deregister(self, name: str) -> bool:
        with self._lock:
            return self._tools.pop(name, None) is not None

    def get(self, name: str, agent_id: str | None = None) -> ToolRegistration:
        with self._lock:
            item = self._tools.get(name)
        if item is None:
            raise KeyError(f"Tool '{name}' is not registered")
        if item.agents is not None and agent_id not in item.agents:
            raise PermissionError(f"Tool '{name}' is not enabled for this agent")
        return item

    def list(self, agent_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._tools.values())
        return [{"name": item.name, "description": item.description} for item in items if item.agents is None or agent_id in item.agents]


registry = ToolRegistry()
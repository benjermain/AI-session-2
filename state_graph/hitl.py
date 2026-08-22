from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from mcp_server.db_client import insert_hitl_task, resolve_hitl_task


@dataclass
class HITLPause(Exception):
    task_id: str
    workflow: str
    state: dict[str, Any]

    def __str__(self) -> str:
        return f"Workflow paused for HITL approval: {self.task_id}"


class HITLNode:
    """A durable approval boundary that preserves the complete workflow state."""

    def __init__(self, workflow: str, requested_by: Optional[str] = None, predicate: Optional[Callable[[Mapping[str, Any]], bool]] = None):
        self.workflow = workflow
        self.requested_by = requested_by
        self.predicate = predicate or (lambda state: True)

    @staticmethod
    def serialize_state(state: Mapping[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(dict(state), default=str))

    def __call__(self, state: Mapping[str, Any]) -> dict[str, Any]:
        snapshot = self.serialize_state(state)
        if not self.predicate(snapshot):
            return snapshot
        task_id = insert_hitl_task(self.workflow, snapshot, self.requested_by)
        raise HITLPause(task_id, self.workflow, snapshot)

    def resume(self, task_id: str, approved: bool, state: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        return resolve_hitl_task(task_id, "APPROVED" if approved else "REJECTED", self.serialize_state(state) if state else None)
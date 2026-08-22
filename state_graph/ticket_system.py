from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from mcp_server.db_client import close_failure_ticket, get_failure_ticket, insert_failure_ticket


@dataclass(frozen=True)
class FailureTicket:
    ticket_id: str
    workflow: str
    node: Optional[str]
    error: str
    state: dict[str, Any]


class FailureTicketEngine:
    """Converts unexpected node failures into durable, resumable tickets."""

    def __init__(self, workflow: str):
        self.workflow = workflow

    def run(self, node: str, state: Mapping[str, Any], operation: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        snapshot = dict(state)
        try:
            return operation(snapshot)
        except Exception as error:
            ticket_id = insert_failure_ticket(self.workflow, str(error), snapshot, node)
            return {"status": "FAILED", "ticket_id": ticket_id, "workflow": self.workflow, "node": node, "error": str(error), "state": snapshot}

    def open(self, node: str, state: Mapping[str, Any], error: Exception) -> FailureTicket:
        snapshot = dict(state)
        ticket_id = insert_failure_ticket(self.workflow, str(error), snapshot, node)
        return FailureTicket(ticket_id, self.workflow, node, str(error), snapshot)

    def resume(self, ticket_id: str, operation: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        ticket = get_failure_ticket(ticket_id)
        if ticket["status"] != "OPEN":
            raise ValueError(f"Failure ticket '{ticket_id}' is already resolved")
        result = operation(dict(ticket["state"]))
        close_failure_ticket(ticket_id)
        return {"status": "RESUMED", "ticket_id": ticket_id, "result": result}
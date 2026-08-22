from __future__ import annotations

from typing import Any, Mapping, Optional

from mcp_server.db_client import get_payload_by_id
from planning.llm_adapter import LLMAdapter
from planning.tree_of_thoughts import tree_of_thoughts
from state_graph.hitl import HITLNode, HITLPause
from state_graph.ticket_system import FailureTicketEngine


class BiosafetyEscalationWorkflow:
    """Policy-gated workflow for payloads requiring institutional review."""

    ALLOWED_DIAGNOSTICS = frozenset({"validate_sequence", "check_payload_risk", "retrieve_ibc_policy"})

    def __init__(self, llm: Any = None, requested_by: Optional[str] = None):
        self.llm = llm or LLMAdapter(mock_mode=True)
        self.hitl = HITLNode("biosafety_escalation", requested_by)
        self.failures = FailureTicketEngine("biosafety_escalation")

    def constrained_react(self, state: Mapping[str, Any]) -> dict[str, Any]:
        actions = list(state.get("diagnostic_actions", ["validate_sequence", "check_payload_risk", "retrieve_ibc_policy"]))
        if any(action not in self.ALLOWED_DIAGNOSTICS for action in actions):
            raise ValueError("Diagnostic action is not whitelisted")
        sequence = str(state.get("sequence", "")).upper()
        payload = get_payload_by_id(int(state["payload_id"]))
        if payload is None:
            raise ValueError("Payload not found")
        return {**dict(state), "sequence_valid": bool(sequence) and set(sequence) <= set("ATCG"), "risk_tier": payload["risk_tier"], "diagnostics": actions}

    def risk_mitigation_paths(self, state: Mapping[str, Any]) -> dict[str, Any]:
        problem = f"Mitigate biosafety risk for Risk Tier {state['risk_tier']} sequence review."
        thoughts = tree_of_thoughts(problem, self.llm, depth=1, beam_width=2)
        return {**dict(state), "mitigation_paths": [{"path": item.state, "score": item.score} for item in thoughts]}

    def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        current = dict(state)
        for node_name, node in (("constrained_react", self.constrained_react), ("risk_mitigation", self.risk_mitigation_paths)):
            result = self.failures.run(node_name, current, node)
            if result.get("status") == "FAILED":
                return result
            current = result
        if current.get("risk_tier", 0) >= 3:
            current["ibc_policy_gate"] = "REQUIRED"
            try:
                return self.hitl(current)
            except HITLPause as pause:
                return {"status": "PAUSED", "task_id": pause.task_id, "workflow": pause.workflow, "state": pause.state}
        current["status"] = "APPROVED"
        return current

    def resume(self, task_id: str, approved: bool, state: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        result = self.hitl.resume(task_id, approved, state)
        result["status"] = "APPROVED" if approved else "REJECTED"
        return result
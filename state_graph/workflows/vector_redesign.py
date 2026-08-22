from __future__ import annotations

from typing import Any, Mapping

from planning.grounded_environment import GroundedEnvironment
from planning.lats import lats
from planning.llm_adapter import LLMAdapter
from state_graph.ticket_system import FailureTicketEngine


class VectorRedesignWorkflow:
    """Iterative, simulation-only vector redesign with grounded safety checks."""

    ALLOWED_ASSAYS = frozenset({"sequence_schema", "off_target_simulation", "bsl_clearance"})

    def __init__(self, llm: Any = None, environment: Any = None, max_iterations: int = 5):
        self.llm = llm or LLMAdapter(mock_mode=True)
        self.environment = environment or GroundedEnvironment()
        self.max_iterations = max_iterations
        self.failures = FailureTicketEngine("vector_redesign")

    def constrained_react_assay(self, state: Mapping[str, Any]) -> dict[str, Any]:
        assays = list(state.get("assays", ["sequence_schema", "off_target_simulation", "bsl_clearance"]))
        if any(assay not in self.ALLOWED_ASSAYS for assay in assays):
            raise ValueError("Assay is not whitelisted")
        sequence = str(state["sequence"]).upper()
        if not sequence or not set(sequence) <= set("ATCG"):
            raise ValueError("Sequence must contain only A, C, T, and G")
        score = round(0.05 + (len(sequence) % 7) * 0.04, 3)
        return {**dict(state), "sequence": sequence, "off_target_score": score, "assays": assays}

    def lats_mutation_search(self, state: Mapping[str, Any]) -> dict[str, Any]:
        task = f"Find a safer simulated vector state for payload_id {state.get('payload_id', 1)} using sequence {state['sequence']} with BSL-3 and Risk Tier 1."
        result = lats(task, self.llm, self.environment, iterations=1, n_actions=2)
        return {**dict(state), "lats_success": result.success, "lats_best_state": result.output, "lats_score": result.best_score}

    def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        current = dict(state)
        for iteration in range(1, self.max_iterations + 1):
            current["iteration"] = iteration
            checked = self.failures.run("constrained_react_assay", current, self.constrained_react_assay)
            if checked.get("status") == "FAILED":
                return checked
            current = checked
            if current["off_target_score"] < float(current.get("safety_threshold", 0.40)):
                current["status"] = "SAFE"
                return current
            searched = self.failures.run("lats_mutation_search", current, self.lats_mutation_search)
            if searched.get("status") == "FAILED":
                return searched
            current = searched
            sequence = current["sequence"]
            current["sequence"] = sequence[:-1] if len(sequence) > 4 else sequence + "A"
        current["status"] = "UNRESOLVED"
        return current
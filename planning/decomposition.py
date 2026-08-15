from __future__ import annotations

from collections import deque
from typing import Any, Callable

from .models import PlanDAG, SubTask


class DecompositionEngine:
    """Precomputes a DAG for a target request and executes it in topological order."""

    def __init__(self) -> None:
        self._token_budget = 0

    def decompose(self, request: str, payload_id: int | None = None) -> PlanDAG:
        lowered = request.lower()
        subtasks = [
            SubTask(
                id="bsl_validation",
                name="bsl_validation",
                description="Validate researcher BSL clearance for the requested payload and lab context.",
                dependencies=[],
                metadata={"payload_id": payload_id, "stage": "safety"},
            ),
            SubTask(
                id="payload_validation",
                name="payload_validation",
                description="Confirm the payload format, nucleotide schema, and risk metadata are valid before synthesis.",
                dependencies=["bsl_validation"],
                metadata={"payload_id": payload_id, "stage": "validation"},
            ),
        ]

        if "off-target" in lowered or "simulate" in lowered or "risk" in lowered:
            subtasks.append(
                SubTask(
                    id="off_target_scan",
                    name="off_target_scan",
                    description="Run off-target alignment and risk simulation to evaluate unintended binding events.",
                    dependencies=["payload_validation"],
                    metadata={"payload_id": payload_id, "stage": "simulation"},
                )
            )

        subtasks.append(
            SubTask(
                id="finalize_plan",
                name="finalize_plan",
                description="Summarize the validated biosafety and payload results into an actionable lab recommendation.",
                dependencies=[subtask.id for subtask in subtasks],
                metadata={"payload_id": payload_id, "stage": "reporting"},
            )
        )

        dag = PlanDAG(subtasks=subtasks)
        return dag

    def execute_plan(self, plan: PlanDAG, executor: Callable[[SubTask], dict[str, Any]]) -> dict[str, Any]:
        order = plan.execution_order()
        results: list[dict[str, Any]] = []
        total_tokens = 0

        for task_id in order:
            task = plan.subtask_by_id(task_id)
            result = executor(task)
            results.append({"task_id": task_id, "result": result})
            total_tokens += self._estimate_tokens(str(result))

        per_task = {}
        for task_id in order:
            item = next(entry for entry in results if entry["task_id"] == task_id)
            per_task[task_id] = self._estimate_tokens(str(item["result"]))

        return {
            "execution_order": order,
            "results": results,
            "token_usage": {"total_tokens": total_tokens, "per_task": per_task},
        }

    def _estimate_tokens(self, value: str) -> int:
        return max(1, len(value) // 4)


__all__ = ["DecompositionEngine"]

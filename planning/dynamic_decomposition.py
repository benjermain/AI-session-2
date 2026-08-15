from __future__ import annotations

from collections import deque
from typing import Any, Callable

from .decomposition import DecompositionEngine
from .models import PlanDAG, SubTask


class DynamicDecompositionEngine:
    """Replans after observing task outcomes, especially when failed safety/simulation checks occur."""

    def __init__(self, decomposition_engine: DecompositionEngine | None = None) -> None:
        self.decomposition_engine = decomposition_engine or DecompositionEngine()

    def run(self, request: str, executor: Callable[[SubTask], dict[str, Any]]) -> dict[str, Any]:
        plan = self.decomposition_engine.decompose(request)
        ready = deque(plan.execution_order())
        history: list[dict[str, Any]] = []
        replans = 0

        while ready:
            task_id = ready.popleft()
            task = plan.subtask_by_id(task_id)
            result = executor(task)
            history.append({"task_id": task_id, "result": result})

            if self._requires_replan(result, task_id):
                replans += 1
                fallback = SubTask(
                    id="adaptive_off_target_retest",
                    name="adaptive_off_target_retest",
                    description="Re-plan after failed off-target validation by narrowing the target and repeating the simulation with adjusted constraints.",
                    dependencies=[task_id],
                    metadata={"reason": "off_target_failure", "source_task": task_id},
                )
                history.append({"task_id": fallback.id, "result": {"status": "replanned", "reason": "off-target simulation failed; adjusted strategy selected"}})
                ready.appendleft(fallback.id)
                plan = PlanDAG(subtasks=[*plan.subtasks, fallback])
                continue

            if task_id == "finalize_plan":
                break

        return {
            "plan": plan.model_dump(),
            "replans": replans,
            "execution_history": history,
        }

    def _requires_replan(self, result: dict[str, Any], task_id: str) -> bool:
        if not isinstance(result, dict):
            return False
        if result.get("status") == "failed":
            return True
        if result.get("off_target") is True:
            return True
        if result.get("unexpected") is True:
            return True
        if task_id == "off_target_scan" and result.get("risk_level") in {"high", "critical"}:
            return True
        return False


__all__ = ["DynamicDecompositionEngine"]

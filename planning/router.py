from __future__ import annotations

from enum import Enum
from typing import Any
from .plan_and_solve import plan_and_solve
from .tree_of_thoughts import tree_of_thoughts
from .lats import lats


class TaskType(str, Enum):
    PLAN_AND_SOLVE = "plan_and_solve"
    TREE_OF_THOUGHTS = "tree_of_thoughts"
    LATS = "lats"


def classify_subtask(instruction: str) -> TaskType:
    """
    Classifies a sub-task instruction based on its domain structure:
    - Linear / Deterministic -> Plan-and-Solve
    - Sequence Optimization / Candidate Ranking -> Tree of Thoughts
    - Equipment Scheduling / High-Risk Slot Allocation -> LATS
    """
    inst_lower = instruction.lower()
    if any(keyword in inst_lower for keyword in ["schedule", "equipment", "slot", "reshuffle", "batch", "allocate"]):
        return TaskType.LATS
    elif any(keyword in inst_lower for keyword in ["optimize", "sequence", "codon", "primer", "rank", "candidate"]):
        return TaskType.TREE_OF_THOUGHTS
    else:
        return TaskType.PLAN_AND_SOLVE


def route_subtask(
    instruction: str,
    context: str,
    llm: Any,
    environment: Any = None,
    task_type_override: TaskType | None = None,
) -> dict[str, Any]:
    """
    Routes a sub-task to the appropriate planning algorithm based on structural fit.
    Returns a dictionary containing the chosen algorithm, output, and metadata.
    """
    task_type = task_type_override or classify_subtask(instruction)
    problem = f"Instruction: {instruction}\nContext: {context}"

    if task_type == TaskType.PLAN_AND_SOLVE:
        result = plan_and_solve(problem, llm)
        return {
            "algorithm": TaskType.PLAN_AND_SOLVE.value,
            "output": result,
            "success": True,
        }
    elif task_type == TaskType.TREE_OF_THOUGHTS:
        thoughts = tree_of_thoughts(problem, llm, depth=2, beam_width=2)
        best_thought = max(thoughts, key=lambda t: t.score) if thoughts else None
        output = best_thought.state if best_thought else "No valid thought branch found."
        return {
            "algorithm": TaskType.TREE_OF_THOUGHTS.value,
            "output": output,
            "score": best_thought.score if best_thought else 0.0,
            "thoughts": [t.model_dump() for t in thoughts],
            "success": True if best_thought and best_thought.score >= 0.5 else False,
        }
    elif task_type == TaskType.LATS:
        if environment is None:
            raise ValueError("Environment evaluator is required for LATS routing")
        lats_result = lats(problem, llm, environment, iterations=2, n_actions=2)
        return {
            "algorithm": TaskType.LATS.value,
            "output": lats_result.output,
            "score": lats_result.best_score,
            "iterations": lats_result.iterations,
            "success": lats_result.success,
        }
    else:
        raise ValueError(f"Unknown task type: {task_type}")

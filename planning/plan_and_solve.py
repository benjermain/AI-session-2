from __future__ import annotations

from typing import Any


def plan_and_solve(problem: str, llm: Any) -> str:
    """
    Plan-and-Solve:
    Explicit two-phase prompt (Phase 1: explicit step-by-step plan, Phase 2: execution).
    Directly adapted from AmrSheta22/task_decomposition_and_planning reference toolkit.
    """
    response = llm.invoke([
        ("system", "You are a precise Plan-and-Solve agent. First devise a step-by-step plan, then solve the problem systematically."),
        ("human", f"""Problem: {problem}

Let's first devise a plan step-by-step to solve this task, then carry out the plan and provide the final answer."""),
    ], temperature=0.1)

    result = response.content
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError("The chat model returned an empty response")
    return result.strip()

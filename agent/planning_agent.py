from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from planning.decomposition import DecompositionEngine
from planning.dynamic_decomposition import DynamicDecompositionEngine


class PlanningAgent:
    def __init__(self) -> None:
        self.decomposition_engine = DecompositionEngine()
        self.dynamic_engine = DynamicDecompositionEngine(self.decomposition_engine)

    def plan(self, request: str, payload_id: int | None = None) -> dict[str, Any]:
        return self.decomposition_engine.decompose(request, payload_id=payload_id).model_dump()

    def dynamic_plan(self, request: str, executor: Callable | None = None) -> dict[str, Any]:
        executor = executor or self._default_executor
        return self.dynamic_engine.run(request, executor=executor)

    def _default_executor(self, task):
        if task.id == "off_target_scan":
            return {"task_id": task.id, "status": "ok", "off_target": False, "risk_level": "low"}
        return {"task_id": task.id, "status": "ok"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vellora planning agent with DAG decomposition and dynamic replanning.")
    parser.add_argument("--request", type=str, default="Validate the payload and run a biosafety simulation before approval.", help="Request to decompose into a DAG.")
    parser.add_argument("--payload-id", type=int, default=42, help="Optional payload ID to associate with the plan.")
    parser.add_argument("--dynamic", action="store_true", help="Use the dynamic interleaved planner that re-evaluates after task output.")
    parser.add_argument("--interactive", action="store_true", help="Run the interactive planning loop in the terminal.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    agent = PlanningAgent()

    if args.interactive:
        while True:
            request = input("Enter a planning request or 'exit': ").strip()
            if request.lower() in {"exit", "quit"}:
                break
            result = agent.dynamic_plan(request) if args.dynamic else agent.plan(request, args.payload_id)
            print(json.dumps(result, indent=2))
        return

    result = agent.dynamic_plan(args.request) if args.dynamic else agent.plan(args.request, args.payload_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

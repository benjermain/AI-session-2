from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Optional

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Thought(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class EnvironmentFeedback(BaseModel):
    """A grounded signal produced outside the language model."""

    success: bool
    score: float = Field(ge=0.0, le=1.0)
    details: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")


class SubTask(BaseModel):
    """A single atomic unit in a planning DAG."""

    id: str
    name: str
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_self_dependency(self):
        if self.id in self.dependencies:
            raise ValueError(f"SubTask '{self.id}' cannot depend on itself.")
        return self


class PlanDAG(BaseModel):
    """A plan expressed as a DAG of dependent subtasks."""

    subtasks: list[SubTask] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_subtask_graph(self):
        ids = [task.id for task in self.subtasks]
        duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
        if duplicates:
            raise ValueError(f"Duplicate subtask ids found: {duplicates}")

        dependency_ids = {dep for task in self.subtasks for dep in task.dependencies}
        missing = sorted(dependency_ids - set(ids))
        if missing:
            raise ValueError(f"Subtask dependencies reference unknown ids: {missing}")

        self.validate_acyclic()
        return self

    def validate_acyclic(self) -> bool:
        graph = nx.DiGraph()
        for task in self.subtasks:
            graph.add_node(task.id)
        for task in self.subtasks:
            for dependency in task.dependencies:
                graph.add_edge(dependency, task.id)

        if not nx.is_directed_acyclic_graph(graph):
            cycles = [list(cycle) for cycle in nx.simple_cycles(graph)]
            raise ValueError(f"Cyclic dependency detected in PlanDAG: {cycles}")
        return True

    def execution_order(self) -> list[str]:
        self.validate_acyclic()

        dependents: dict[str, list[str]] = defaultdict(list)
        indegree: dict[str, int] = {task.id: 0 for task in self.subtasks}

        for task in self.subtasks:
            for dependency in task.dependencies:
                dependents[dependency].append(task.id)
                indegree[task.id] += 1

        ready = deque(sorted(task_id for task_id, degree in indegree.items() if degree == 0))
        order: list[str] = []

        while ready:
            current = ready.popleft()
            order.append(current)
            for nxt in sorted(dependents.get(current, [])):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)

        if len(order) != len(self.subtasks):
            raise ValueError("PlanDAG contains a cycle and cannot be topologically sorted.")
        return order

    def subtask_by_id(self, task_id: str) -> SubTask:
        for task in self.subtasks:
            if task.id == task_id:
                return task
        raise KeyError(f"SubTask '{task_id}' not found in PlanDAG")

    def model_dump(self, **kwargs):
        return super().model_dump(**kwargs)


@dataclass
class LATSNode:
    state: str
    action: str = "root"
    parent: Optional["LATSNode"] = field(default=None, repr=False)
    children: list["LATSNode"] = field(default_factory=list, repr=False)
    visits: int = 0
    value_sum: float = 0.0
    environment_score: float = 0.0
    model_score: float = 0.0
    feedback: Optional[EnvironmentFeedback] = None
    reflections: list[str] = field(default_factory=list)

    @property
    def mean_value(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass
class LATSResult:
    success: bool
    output: str
    best_score: float
    iterations: int
    root: LATSNode

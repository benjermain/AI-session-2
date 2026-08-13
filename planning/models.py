from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


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

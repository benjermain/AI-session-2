from __future__ import annotations

import json
import time
from typing import Any, Type, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMCallMetrics:
    """Tracks LLM calls, input/output tokens, and cumulative latency for evaluation."""

    def __init__(self):
        self.call_count: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_latency_seconds: float = 0.0

    def record_call(self, prompt: str, response: str, latency: float):
        self.call_count += 1
        # Standard token heuristic (~4 characters per token)
        self.prompt_tokens += max(1, len(prompt) // 4)
        self.completion_tokens += max(1, len(response) // 4)
        self.total_latency_seconds += latency

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def reset(self):
        self.call_count = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_latency_seconds = 0.0


class StructuredResponseWrapper:
    def __init__(self, content: str):
        self.content = content


class LLMAdapter:
    """
    Adapter that connects the codebase LLM model to AmrSheta's reference toolkit expectations.
    Implements with_structured_output(..., method='json_schema') and tracks metrics.
    """

    def __init__(self, base_llm: Any = None, mock_mode: bool = False):
        self.base_llm = base_llm
        self.mock_mode = mock_mode
        self.metrics = LLMCallMetrics()

    def invoke(self, messages: list[tuple[str, str]], temperature: float = 0.2) -> StructuredResponseWrapper:
        start_time = time.time()
        prompt_str = "\n".join(f"{role}: {content}" for role, content in messages)

        if self.mock_mode or self.base_llm is None:
            response_text = self._mock_invoke(prompt_str)
        else:
            try:
                result = self.base_llm.invoke(messages, temperature=temperature)
                response_text = result.content if hasattr(result, "content") else str(result)
            except Exception:
                response_text = self._mock_invoke(prompt_str)

        elapsed = time.time() - start_time
        self.metrics.record_call(prompt_str, response_text, elapsed)
        return StructuredResponseWrapper(response_text)

    def with_structured_output(self, schema_cls: Type[T], method: str = "json_schema"):
        class BoundStructuredLLM:
            def __init__(self, parent: LLMAdapter, schema: Type[T]):
                self.parent = parent
                self.schema = schema

            def invoke(self, messages: list[tuple[str, str]], temperature: float = 0.2) -> T:
                start_time = time.time()
                prompt_str = "\n".join(f"{role}: {content}" for role, content in messages)

                if self.parent.mock_mode or self.parent.base_llm is None:
                    parsed_obj = self.parent._mock_structured_invoke(prompt_str, self.schema)
                    response_text = json.dumps(parsed_obj.model_dump())
                else:
                    try:
                        bound = self.parent.base_llm.with_structured_output(self.schema, method=method)
                        parsed_obj = bound.invoke(messages, temperature=temperature)
                        response_text = json.dumps(parsed_obj.model_dump())
                    except Exception:
                        parsed_obj = self.parent._mock_structured_invoke(prompt_str, self.schema)
                        response_text = json.dumps(parsed_obj.model_dump())

                elapsed = time.time() - start_time
                self.parent.metrics.record_call(prompt_str, response_text, elapsed)
                return parsed_obj

        return BoundStructuredLLM(self, schema_cls)

    def _mock_invoke(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "plan-and-solve" in prompt_lower or "devise a plan" in prompt_lower:
            return "Step 1: Validate researcher BSL clearance against BSL-3 rules. Step 2: Validate genetic sequence schema ATCG characters. Step 3: Complete verification."
        if "reflection" in prompt_lower or "failed" in prompt_lower:
            return "I allocated equipment line B-202 without checking supervisor BSL-3 authorization. Next trial I must verify BSL clearance prior to slot submission."
        return "Step completed: Parameters validated and verified against biosafety policy rules."

    def _mock_structured_invoke(self, prompt: str, schema_cls: Type[T]) -> Any:
        schema_name = schema_cls.__name__
        prompt_lower = prompt.lower()

        if schema_name == "ThoughtCandidates":
            return schema_cls(candidates=[
                "Candidate A: ATGCGATCGATCGATCGATCGATCGATCGATC (Balanced GC 50%, no hairpin)",
                "Candidate B: ATGCGCGCGCGCGCGCGCGCGCGCATATAT (High GC 72%, potential secondary hairpin)"
            ])
        elif schema_name == "ThoughtEvaluation":
            if "high gc" in prompt_lower or "hairpin" in prompt_lower or "candidate b" in prompt_lower:
                return schema_cls(score=0.35, rationale="Excessive GC content (72%) increases hairpin kinetic binding risk.")
            return schema_cls(score=0.91, rationale="Balanced GC content (50%) and clean off-target safety profile.")
        elif schema_name == "LATSActionBatch":
            return schema_cls(actions=[
                {"action": "Assign Slot Line-A-101 with BSL-3 clearance", "state": "Slot Line-A-101 assigned, researcher Dr. Vance BSL-3 verified, Off-target score 0.04"},
                {"action": "Assign Slot Line-B-202 unverified", "state": "Slot Line-B-202 assigned, BSL clearance unverified"}
            ])
        elif schema_name == "ValueEstimate":
            if "unverified" in prompt_lower:
                return schema_cls(score=0.25)
            return schema_cls(score=0.89)
        else:
            try:
                return schema_cls()
            except Exception:
                raise ValueError(f"No mock generator for schema: {schema_name}")

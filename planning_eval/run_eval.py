"""
Issue #11: Build Evaluation Suite & Benchmark Runner (planning_eval/run_eval.py)

Quantitative comparison across accuracy, LLM calls, tokens, latency, and estimated cost.
Produces JSON trace exporter to artifacts/ and automated benchmark table generation.
"""

from __future__ import annotations

import json
import time
import os
from typing import Any
from dataclasses import dataclass, asdict
from planning.llm_adapter import LLMCallMetrics
from planning.models import EnvironmentFeedback


@dataclass
class EvalMetrics:
    """Metrics for a single evaluation run."""

    method: str
    test_name: str
    success: bool
    accuracy_score: float
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_seconds: float
    estimated_cost_usd: float

    @staticmethod
    def from_llm_metrics(
        method: str,
        test_name: str,
        success: bool,
        accuracy_score: float,
        metrics: LLMCallMetrics,
        latency: float,
        cost_per_1k_input: float = 0.0005,
        cost_per_1k_output: float = 0.0015,
    ) -> EvalMetrics:
        """Create EvalMetrics from LLMCallMetrics and timing."""
        input_cost = (metrics.prompt_tokens / 1000.0) * cost_per_1k_input
        output_cost = (metrics.completion_tokens / 1000.0) * cost_per_1k_output
        total_cost = input_cost + output_cost

        return EvalMetrics(
            method=method,
            test_name=test_name,
            success=success,
            accuracy_score=accuracy_score,
            llm_calls=metrics.call_count,
            prompt_tokens=metrics.prompt_tokens,
            completion_tokens=metrics.completion_tokens,
            total_tokens=metrics.total_tokens,
            latency_seconds=latency,
            estimated_cost_usd=total_cost,
        )


class BenchmarkSuite:
    """Fixed suite of test cases for evaluating planning algorithms."""

    def __init__(self):
        self.tests = [
            {
                "name": "synthesis_job_bsl_validation",
                "description": "Researcher BSL-2 attempting Risk Tier 3 payload (should fail)",
                "task": "Validate synthesis job submission for researcher_id=2, payload_id=3, sequence=ATCGATCG",
                "expected_success": False,
            },
            {
                "name": "synthesis_job_safe_approval",
                "description": "Researcher BSL-4 attempting Risk Tier 1 payload (should succeed)",
                "task": "Validate synthesis job submission for researcher_id=4, payload_id=1, sequence=ATCGATCG",
                "expected_success": True,
            },
            {
                "name": "equipment_slot_allocation",
                "description": "Schedule high-risk payload to available lab equipment",
                "task": "Allocate slot for BSL-3 equipment Line-A-101 with researcher BSL-3 clearance",
                "expected_success": True,
            },
            {
                "name": "sequence_optimization_codon",
                "description": "Optimize genetic sequence for codon usage",
                "task": "Design codon-optimized sequence with balanced GC content (50%) and no hairpins",
                "expected_success": True,
            },
            {
                "name": "off_target_alignment_risk",
                "description": "Evaluate off-target alignment risk (high risk, should fail safety check)",
                "task": "Evaluate sequence ATATAT for genome-wide alignment (expected high off-target score 0.8)",
                "expected_success": False,
            },
        ]

    def get_tests(self) -> list[dict]:
        """Return all test cases."""
        return self.tests

    def get_test_by_name(self, name: str) -> dict | None:
        """Get a specific test by name."""
        for test in self.tests:
            if test["name"] == name:
                return test
        return None


class BenchmarkRunner:
    """Execute benchmark suite across multiple planning methods."""

    def __init__(self, output_dir: str = "artifacts"):
        self.output_dir = output_dir
        self.suite = BenchmarkSuite()
        self.results: list[EvalMetrics] = []
        os.makedirs(output_dir, exist_ok=True)

    def run_method_on_test(
        self,
        method_name: str,
        test_case: dict,
        executor_func: Any,
    ) -> EvalMetrics:
        """
        Execute a planning method on a single test case.
        
        Args:
            method_name: Name of planning method (e.g., "LATS", "Self-Refine", "Reflexion")
            test_case: Test case dict with 'name', 'task', 'expected_success'
            executor_func: Callable that runs the method and returns (success, accuracy_score, metrics, latency)
        
        Returns:
            EvalMetrics for this run.
        """
        start_time = time.time()
        try:
            success, accuracy_score, llm_metrics, latency = executor_func(test_case)
        except Exception as e:
            print(f"Error executing {method_name} on {test_case['name']}: {e}")
            success = False
            accuracy_score = 0.0
            llm_metrics = LLMCallMetrics()
            latency = time.time() - start_time

        metrics = EvalMetrics.from_llm_metrics(
            method=method_name,
            test_name=test_case["name"],
            success=success,
            accuracy_score=accuracy_score,
            metrics=llm_metrics,
            latency=latency,
        )
        self.results.append(metrics)
        return metrics

    def run_all_methods(
        self,
        method_executors: dict[str, Any],
    ):
        """
        Run all methods on all test cases.
        
        Args:
            method_executors: Dict mapping method_name -> executor_func
        """
        tests = self.suite.get_tests()
        for method_name, executor_func in method_executors.items():
            for test_case in tests:
                print(f"Running {method_name} on {test_case['name']}...")
                self.run_method_on_test(method_name, test_case, executor_func)

    def export_json_traces(self) -> str:
        """Export results as JSON traces to artifacts/eval_traces.json."""
        trace_path = os.path.join(self.output_dir, "eval_traces.json")
        traces = [asdict(m) for m in self.results]
        with open(trace_path, "w") as f:
            json.dump(traces, f, indent=2)
        print(f"Exported {len(traces)} trace records to {trace_path}")
        return trace_path

    def generate_benchmark_table(self) -> str:
        """
        Generate a comparison table in Markdown format.
        Groups results by method, calculates aggregates.
        """
        if not self.results:
            return "No results to report."

        # Group by method
        by_method: dict[str, list[EvalMetrics]] = {}
        for result in self.results:
            if result.method not in by_method:
                by_method[result.method] = []
            by_method[result.method].append(result)

        # Compute aggregates per method
        aggregates: dict[str, dict] = {}
        for method, results in by_method.items():
            pass_count = sum(1 for r in results if r.success)
            accuracy_avg = sum(r.accuracy_score for r in results) / len(results) if results else 0.0
            calls_avg = sum(r.llm_calls for r in results) / len(results) if results else 0
            tokens_avg = sum(r.total_tokens for r in results) / len(results) if results else 0
            latency_avg = sum(r.latency_seconds for r in results) / len(results) if results else 0.0
            cost_total = sum(r.estimated_cost_usd for r in results)

            aggregates[method] = {
                "tests_passed": f"{pass_count}/{len(results)}",
                "accuracy": f"{accuracy_avg:.2f}",
                "llm_calls": f"{calls_avg:.1f}",
                "tokens": f"{tokens_avg:.0f}",
                "latency_s": f"{latency_avg:.2f}",
                "cost_usd": f"${cost_total:.4f}",
            }

        # Build markdown table
        table_lines = [
            "| Method | Tests Passed | Accuracy | Avg LLM Calls | Avg Tokens | Avg Latency (s) | Total Cost (USD) |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for method in sorted(aggregates.keys()):
            agg = aggregates[method]
            table_lines.append(
                f"| {method} | {agg['tests_passed']} | {agg['accuracy']} | {agg['llm_calls']} | {agg['tokens']} | {agg['latency_s']} | {agg['cost_usd']} |"
            )

        return "\n".join(table_lines)

    def save_benchmark_table(self) -> str:
        """Save benchmark table to artifacts/benchmark_table.md."""
        table = self.generate_benchmark_table()
        table_path = os.path.join(self.output_dir, "benchmark_table.md")
        with open(table_path, "w") as f:
            f.write("# Planning Algorithm Benchmark Comparison\n\n")
            f.write(table)
            f.write("\n")
        print(f"Saved benchmark table to {table_path}")
        return table_path

    def run_and_export(self, method_executors: dict[str, Any]) -> dict[str, str]:
        """
        Run full evaluation suite and export all artifacts.
        
        Returns:
            Dict mapping artifact_type -> file_path
        """
        print("Starting benchmark suite...")
        self.run_all_methods(method_executors)

        artifacts = {
            "json_traces": self.export_json_traces(),
            "benchmark_table": self.save_benchmark_table(),
        }
        return artifacts

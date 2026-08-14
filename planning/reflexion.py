"""
Issue #10b: Implement Reflexion Engine (planning/reflexion.py)

Multi-trial cross-attempt verbal memory buffers using episodic memory.
When LATS or other sequences fail grounded checks, Reflexion aggregates
reflections across trials (capped at memory_size=3) and guides future attempts.
"""

from __future__ import annotations

from typing import Any, Optional
from planning.models import LATSNode


class ReflexionMemory:
    """
    Episodic memory buffer for Reflexion: stores attempted trajectories,
    failures, and reflections across multiple trials.
    
    Capacity is capped at memory_size trials to prevent unbounded growth.
    """

    def __init__(self, memory_size: int = 3):
        self.memory_size = memory_size
        self.trials: list[dict] = []

    def record_trial(
        self,
        trial_num: int,
        task: str,
        trajectory: list[str],
        final_state: str,
        success: bool,
        reflections: list[str],
        feedback_details: list[str],
    ):
        """
        Record a trial outcome and its reflections.
        
        Args:
            trial_num: Trial identifier
            task: Original task/problem description
            trajectory: Sequence of states visited
            final_state: Terminal state reached
            success: Whether trial succeeded
            reflections: List of reflection strings (from LLM analysis of failures)
            feedback_details: Grounded evaluation details
        """
        trial_record = {
            "trial_num": trial_num,
            "task": task,
            "trajectory": trajectory,
            "final_state": final_state,
            "success": success,
            "reflections": reflections,
            "feedback_details": feedback_details,
        }
        self.trials.append(trial_record)

        # Enforce capacity limit: keep most recent memory_size trials
        if len(self.trials) > self.memory_size:
            self.trials = self.trials[-self.memory_size :]

    def get_aggregate_reflections(self) -> list[str]:
        """
        Aggregate all reflections from failed trials in memory.
        Returns list of reflection strings to guide next attempt.
        """
        aggregate = []
        for trial in self.trials:
            if not trial["success"]:  # Only include failed trials
                aggregate.extend(trial["reflections"])
        return aggregate

    def get_memory_summary(self) -> str:
        """
        Generate a text summary of memory state for inclusion in prompts.
        """
        if not self.trials:
            return "No prior attempts in memory."

        summary_lines = []
        for i, trial in enumerate(self.trials, 1):
            status = "SUCCESS" if trial["success"] else "FAILED"
            summary_lines.append(f"Trial {trial['trial_num']} [{status}]:")
            if trial["reflections"]:
                for reflection in trial["reflections"]:
                    summary_lines.append(f"  - {reflection}")
            else:
                summary_lines.append("  (No reflections recorded)")

        return "\n".join(summary_lines)

    def clear(self):
        """Clear all trials from memory."""
        self.trials.clear()


class ReflexionResult:
    """Result of a Reflexion attempt."""

    def __init__(
        self,
        success: bool,
        output: str,
        trial_num: int,
        trajectory_length: int,
        memory_used: ReflexionMemory,
    ):
        self.success = success
        self.output = output
        self.trial_num = trial_num
        self.trajectory_length = trajectory_length
        self.memory_used = memory_used


def reflexion(
    task: str,
    llm: Any,
    environment: Any,
    max_trials: int = 3,
    memory_size: int = 3,
) -> ReflexionResult:
    """
    Reflexion: Multi-trial loop with persistent episodic memory.
    
    Each trial:
    1. Generate action (with guidance from prior reflection memory)
    2. Evaluate with grounded environment
    3. If failed, generate reflection and store in memory
    4. Next trial uses aggregated reflections to avoid past mistakes
    
    Args:
        task: Problem/task description
        llm: LLM adapter
        environment: GroundedEnvironment for feedback
        max_trials: Maximum number of attempts
        memory_size: Capacity of episodic memory (typically 3)
    
    Returns:
        ReflexionResult with success status and final output
    """
    memory = ReflexionMemory(memory_size=memory_size)

    for trial_num in range(1, max_trials + 1):
        # Get guidance from prior reflection memory
        aggregate_reflections = memory.get_aggregate_reflections()
        memory_text = memory.get_memory_summary()

        # Generate action with reflection context
        action_prompt = _build_reflexion_action_prompt(
            task, memory_text, aggregate_reflections
        )

        try:
            response = llm.invoke(
                [
                    ("system", "You are solving a task using lessons from prior failed attempts. Incorporate reflections from memory."),
                    ("human", action_prompt),
                ],
                temperature=0.5,
            )
            proposed_state = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            proposed_state = f"Error generating action: {str(e)}"

        # Evaluate with grounded environment
        feedback = environment.evaluate(proposed_state)

        trajectory = [proposed_state]  # Simplified: just the final state

        if feedback.success:
            # Success: record and return
            memory.record_trial(
                trial_num=trial_num,
                task=task,
                trajectory=trajectory,
                final_state=proposed_state,
                success=True,
                reflections=[],
                feedback_details=feedback.details,
            )
            return ReflexionResult(
                success=True,
                output=proposed_state,
                trial_num=trial_num,
                trajectory_length=len(trajectory),
                memory_used=memory,
            )

        # Failed: generate reflection for next trial
        reflection_text = _generate_reflection(
            task, proposed_state, feedback, llm
        )

        memory.record_trial(
            trial_num=trial_num,
            task=task,
            trajectory=trajectory,
            final_state=proposed_state,
            success=False,
            reflections=[reflection_text],
            feedback_details=feedback.details,
        )

    # All trials exhausted without success
    return ReflexionResult(
        success=False,
        output="Failed to find valid solution after max trials.",
        trial_num=max_trials,
        trajectory_length=0,
        memory_used=memory,
    )


def _build_reflexion_action_prompt(
    task: str, memory_summary: str, aggregate_reflections: list[str]
) -> str:
    """Build prompt for action generation with memory context."""
    reflections_text = (
        "\n".join(f"  - {r}" for r in aggregate_reflections)
        if aggregate_reflections
        else "  (None yet)"
    )

    return f"""Task:
{task}

Prior Trial Memory (last {len(aggregate_reflections)} reflections):
{memory_summary}

Lessons to avoid:
{reflections_text}

Generate a COMPLETE, VALID solution state that avoids the above mistakes.
Write only the state proposal, no explanation."""


def _generate_reflection(
    task: str, failed_state: str, feedback: Any, llm: Any
) -> str:
    """Generate a reflection on why the state failed."""
    details_str = "\n".join(f"  - {d}" for d in feedback.details)

    prompt = f"""Task:
{task}

Failed Attempt:
{failed_state}

Grounded Feedback (score {feedback.score:.2f}):
{details_str}

Write a concise (1-2 sentence) reflection on what went wrong and how to avoid it next time."""

    try:
        response = llm.invoke(
            [
                ("system", "Generate a brief reflection on failure."),
                ("human", prompt),
            ],
            temperature=0.2,
        )
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        return "Reflection generation failed; approach differently next time."

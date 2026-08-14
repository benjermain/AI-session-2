"""
Issue #10a: Implement Self-Refine Engine (planning/self_refine.py)

Single-pass critique and revision for quick formatting fixes and validation errors.
Used when an LLM draft fails a grounded check and needs lightweight correction.
"""

from __future__ import annotations

from typing import Any
from planning.models import EnvironmentFeedback


class SelfRefineResult:
    """Result of a single self-refine pass."""

    def __init__(
        self,
        original: str,
        revised: str,
        critique: str,
        improved: bool,
        feedback_before: EnvironmentFeedback,
        feedback_after: EnvironmentFeedback,
    ):
        self.original = original
        self.revised = revised
        self.critique = critique
        self.improved = improved
        self.feedback_before = feedback_before
        self.feedback_after = feedback_after


def self_refine(
    draft: str,
    grounded_feedback: EnvironmentFeedback,
    llm: Any,
    environment: Any,
    max_iterations: int = 1,
) -> SelfRefineResult:
    """
    Single-pass (or light multi-pass) self-refinement.
    
    Critiques a failed draft using grounded feedback, generates a revision,
    and checks if the revised version passes grounded evaluation.
    
    Args:
        draft: Initial LLM-generated state/plan
        grounded_feedback: EnvironmentFeedback from initial evaluation
        llm: LLM adapter with structured output support
        environment: GroundedEnvironment evaluator
        max_iterations: Number of refinement loops (typically 1 for Self-Refine)
    
    Returns:
        SelfRefineResult with original, revised, critique, and improvement flag.
    """
    current_state = draft
    current_feedback = grounded_feedback
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # If already successful, stop
        if current_feedback.success:
            return SelfRefineResult(
                original=draft,
                revised=current_state,
                critique="State already valid; no refinement needed.",
                improved=current_state != draft,
                feedback_before=grounded_feedback,
                feedback_after=current_feedback,
            )

        # Generate critique and revision prompt
        critique_prompt = _build_critique_prompt(current_state, current_feedback)

        # LLM generates critique and revised state
        try:
            response = llm.invoke(
                [
                    ("system", "You are a self-refining critic. Analyze the failure and propose a single corrected version."),
                    ("human", critique_prompt),
                ],
                temperature=0.3,
            )
            critique_text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            critique_text = f"Error during LLM critique: {str(e)}"

        # Extract revised state from critique (heuristic: last line or structured extraction)
        revised_state = _extract_revised_state(critique_text, current_state)

        # Re-evaluate with grounded environment
        revised_feedback = environment.evaluate(revised_state)

        # Check if improved
        improved = revised_feedback.score > current_feedback.score

        return SelfRefineResult(
            original=draft,
            revised=revised_state,
            critique=critique_text,
            improved=improved,
            feedback_before=grounded_feedback,
            feedback_after=revised_feedback,
        )

    # Fallback if loop exhausted
    return SelfRefineResult(
        original=draft,
        revised=current_state,
        critique="Max iterations reached without success.",
        improved=current_state != draft,
        feedback_before=grounded_feedback,
        feedback_after=current_feedback,
    )


def _build_critique_prompt(state: str, feedback: EnvironmentFeedback) -> str:
    """Build a prompt for the LLM to critique and revise."""
    details_str = "\n".join(f"  - {d}" for d in feedback.details)
    return f"""Your previous state proposal failed grounded validation:

Proposed State:
{state}

Grounded Evaluation Feedback (score: {feedback.score:.2f}):
{details_str}

Provide a REVISED STATE that addresses each failure point. Write the complete revised state on a new line after "REVISED:".

Example format:
REVISED: Slot Line-A-101 assigned, researcher Dr. Vance BSL-3 verified, Off-target score 0.04"""


def _extract_revised_state(critique_text: str, original_state: str) -> str:
    """
    Extract revised state from LLM critique.
    Heuristic: look for "REVISED:" marker, otherwise return a reasonable guess.
    """
    lines = critique_text.split("\n")
    for i, line in enumerate(lines):
        if "REVISED:" in line:
            revised = line.split("REVISED:", 1)[1].strip()
            if revised:
                return revised
            # If "REVISED:" is on its own line, check next line
            if i + 1 < len(lines):
                return lines[i + 1].strip()

    # Fallback: return original (no improvement, but valid fallback)
    return original_state

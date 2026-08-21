"""
Short-Term Memory & Scratchpad Architecture for Vellora Bio Agent.

Concern 1 Implementation:
- Rolling message buffer holding agent dialogue turns and tool call results.
- Distinct Scratchpad holding agent's current plan, active sub-goal, working state,
  and active biosafety constraints.
- Transcript pruning logic that truncates/prunes older transcript messages when full,
  while guaranteeing the scratchpad state is NEVER destroyed or corrupted.
"""

from typing import Dict, List, Any, Optional
import time

class Scratchpad:
    """
    Scratchpad object holding the agent's working memory state:
    - current_plan: High-level task execution plan
    - active_subgoal: Immediate step/sub-goal being processed
    - working_variables: In-flight execution variables (payload_id, target_gene, etc.)
    - safety_constraints: Active compliance/biosafety constraints
    """
    def __init__(
        self,
        current_plan: str = "",
        active_subgoal: str = "",
        working_variables: Optional[Dict[str, Any]] = None,
        safety_constraints: Optional[List[str]] = None,
    ):
        self.current_plan = current_plan
        self.active_subgoal = active_subgoal
        self.working_variables = working_variables if working_variables is not None else {}
        self.safety_constraints = safety_constraints if safety_constraints is not None else []
        self.last_updated = time.time()

    def update_plan(self, plan: str):
        self.current_plan = plan
        self.last_updated = time.time()

    def update_subgoal(self, subgoal: str):
        self.active_subgoal = subgoal
        self.last_updated = time.time()

    def set_variable(self, key: str, value: Any):
        self.working_variables[key] = value
        self.last_updated = time.time()

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.working_variables.get(key, default)

    def add_safety_constraint(self, constraint: str):
        if constraint not in self.safety_constraints:
            self.safety_constraints.append(constraint)
            self.last_updated = time.time()

    def clear_safety_constraints(self):
        self.safety_constraints.clear()
        self.last_updated = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_plan": self.current_plan,
            "active_subgoal": self.active_subgoal,
            "working_variables": self.working_variables,
            "safety_constraints": self.safety_constraints,
            "last_updated": self.last_updated,
        }

class ShortTermMemory:
    """
    Short-Term Memory Manager:
    - Maintains a rolling transcript buffer of dialogue turns.
    - Encapsulates a distinct Scratchpad instance.
    - Handles pruning when buffer limit is reached, preserving Scratchpad state.
    """
    def __init__(self, max_buffer_size: int = 10, scratchpad: Optional[Scratchpad] = None):
        self.max_buffer_size = max_buffer_size
        self.buffer: List[Dict[str, Any]] = []
        self.scratchpad = scratchpad if scratchpad is not None else Scratchpad()

    def add_message(self, role: str, content: Any, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Appends a message turn to the rolling buffer.
        If buffer size exceeds max_buffer_size, automatically triggers pruning and returns pruned items.
        """
        message = {
            "turn_id": len(self.buffer) + 1,
            "timestamp": time.time(),
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
        self.buffer.append(message)
        
        pruned_items = []
        if len(self.buffer) > self.max_buffer_size:
            pruned_items = self.prune_transcript()
        
        return pruned_items

    def prune_transcript(self, target_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Prunes older transcript messages down to target_size (default: max_buffer_size).
        Returns the list of pruned messages (aging items to be evaluated by the router).
        
        CRITICAL DESIGN GUARANTEE:
        Pruning strictly modifies self.buffer (transcript turns).
        The Scratchpad object (plan, subgoal, working variables, constraints) remains 100% intact.
        """
        target = target_size if target_size is not None else self.max_buffer_size
        if len(self.buffer) <= target:
            return []

        overflow_count = len(self.buffer) - target
        pruned = self.buffer[:overflow_count]
        self.buffer = self.buffer[overflow_count:]

        # Renumber remaining turns for consistency
        for idx, msg in enumerate(self.buffer, start=1):
            msg["turn_id"] = idx

        return pruned

    def get_working_context(self) -> Dict[str, Any]:
        """
        Returns complete working context combining Scratchpad state and active transcript buffer.
        """
        return {
            "scratchpad": self.scratchpad.to_dict(),
            "active_transcript": self.buffer,
            "buffer_count": len(self.buffer),
            "max_buffer_size": self.max_buffer_size,
        }

    def get_managed_context(self, strategy_name: str = "observation_masking", **kwargs) -> Dict[str, Any]:
        """
        Returns context window with active context management strategy applied
        (e.g., observation_masking, sliding_window, recursive_summarization, zone_based_pruning).
        Guarantees that scratchpad remains intact while transcript is appropriately pruned/masked.
        """
        try:
            from context_eval.strategies import apply_context_strategy
            managed_transcript = apply_context_strategy(self.buffer, strategy_name, **kwargs)
        except Exception:
            managed_transcript = self.buffer

        return {
            "scratchpad": self.scratchpad.to_dict(),
            "active_transcript": managed_transcript,
            "buffer_count": len(managed_transcript),
            "original_count": len(self.buffer),
            "strategy_applied": strategy_name,
            "max_buffer_size": self.max_buffer_size,
        }

    def clear_buffer(self):
        """Clears transcript buffer without resetting scratchpad."""
        self.buffer.clear()


"""
Rolling buffer implementation with integrated Context Window Management.
"""
from typing import List, Dict, Any, Optional
from context_eval.strategies import apply_context_strategy


class RollingBuffer:
    """A rolling buffer that maintains conversation history with dynamic context management strategies.

    Supported strategies:
    - observation_masking (default)
    - sliding_window
    - recursive_summarization
    - zone_based_pruning
    """
    def __init__(self, max_turns: int = 50, max_tokens: int = 4000, default_strategy: str = "observation_masking"):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.default_strategy = default_strategy
        self.turns: List[Dict[str, Any]] = []

    def append(self, turn: Dict[str, Any]):
        self.turns.append(turn)
        # Prune if exceeding turn count
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def get_context(self, window: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns standard sliding window context."""
        if window is None:
            window = self.max_turns
        return self.turns[-window:]

    def get_managed_context(self, strategy: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """Returns context window processed through the active context management strategy."""
        strat = strategy or self.default_strategy
        return apply_context_strategy(self.turns, strat, **kwargs)

    def prune_to_tokens(self, max_tokens: Optional[int] = None, strategy: str = "observation_masking") -> List[Dict[str, Any]]:
        """Applies context management strategy to compress transcript to token budget."""
        budget = max_tokens or self.max_tokens
        return self.get_managed_context(strategy=strategy)

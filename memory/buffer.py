"""
Simple sliding rolling buffer implementation.
"""
from typing import List, Dict, Any

class RollingBuffer:
    """A simple rolling buffer that keeps the last N turns or up to a token budget.

    Methods:
    - append(turn: dict)
    - get_context(window: int)
    - prune_to_tokens(max_tokens: int)
    """
    def __init__(self, max_turns: int = 50, max_tokens: int = 4000):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.turns: List[Dict[str, Any]] = []

    def append(self, turn: Dict[str, Any]):
        self.turns.append(turn)
        # simple prune by count
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def get_context(self, window: int = None):
        if window is None:
            window = self.max_turns
        return self.turns[-window:]

    def prune_to_tokens(self, max_tokens: int = None):
        # Placeholder: in a real implementation count tokens and prune oldest
        if max_tokens is None:
            max_tokens = self.max_tokens
        # No-op in this simple scaffold
        return

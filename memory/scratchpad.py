"""
Scratchpad: ephemeral reasoning buffer used only for the current agent decision.
Does not get written to episodic or semantic memory unless explicitly promoted.
"""
from typing import List

class Scratchpad:
    def __init__(self):
        self.items: List[str] = []

    def add(self, note: str):
        self.items.append(note)

    def clear(self):
        self.items = []

    def get(self):
        return list(self.items)

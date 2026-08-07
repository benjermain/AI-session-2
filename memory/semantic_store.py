"""
Semantic store: consolidated facts derived from episodic events.
Each entry includes a canonical_fact, supporting_event_ids, contradiction_flag, and last_reviewed.
"""
from typing import List, Dict, Any
import time

class SemanticStore:
    def __init__(self):
        self.entries: List[Dict[str, Any]] = []

    def add_entry(self, canonical_fact: str, supporting_events: List[Dict[str, Any]], metadata: Dict[str, Any] = None):
        entry = {
            'id': len(self.entries) + 1,
            'canonical_fact': canonical_fact,
            'supporting_events': [e.get('id') if 'id' in e else None for e in supporting_events],
            'raw_support': supporting_events,
            'contradiction': False,
            'last_reviewed': time.time(),
        }
        if metadata:
            entry['metadata'] = metadata
        self.entries.append(entry)
        return entry

    def list(self):
        return list(self.entries)

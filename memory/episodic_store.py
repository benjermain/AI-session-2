"""
Episodic store: append-only list of events (visits, tool outputs, notes).
Includes simple query by patient id and time range.
"""
from typing import List, Dict, Any
import time

class EpisodicStore:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    def append(self, event: Dict[str, Any]):
        # event should include: session_id, patient_id, text, metadata
        event = dict(event)
        event.setdefault('created_at', time.time())
        self.events.append(event)
        return event

    def query_by_patient(self, patient_id):
        return [e for e in self.events if e.get('patient_id') == patient_id]

    def all(self):
        return list(self.events)

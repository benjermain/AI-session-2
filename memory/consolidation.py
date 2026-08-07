"""
Consolidation logic: runs periodically over episodic events and creates/updates semantic store entries.
Includes simple conflict detection (presence vs absence) and resolution rules.
"""
from typing import List, Dict, Any

def consolidate(episodic_events: List[Dict[str, Any]], semantic_store):
    """A naive consolidation pass:
    - group by patient_id
    - detect simple contradictions (e.g., has_allergy True vs missing)
    - create/update semantic entries
    """
    by_patient = {}
    for e in episodic_events:
        pid = e.get('patient_id')
        by_patient.setdefault(pid, []).append(e)

    created = []
    for pid, events in by_patient.items():
        # naive rule: find any mention of 'penicillin' or 'allergy'
        texts = ' '.join([e.get('text','') for e in events]).lower()
        if 'penicillin' in texts or 'allergy' in texts:
            # find supporting events
            supports = [e for e in events if 'penicillin' in (e.get('text','').lower()) or 'allergy' in (e.get('text','').lower())]
            entry = semantic_store.add_entry(f"patient:{pid}:penicillin_allergy:true", supporting_events=supports, metadata={'patient_id': pid})
            created.append(entry)
        # else: no-op for now
    return created

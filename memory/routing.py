"""
Routing logic: decide whether to promote an event to episodic or mark as ephemeral or drop.
This is a heuristic-based, easily auditable function required by the rubric.
"""
from typing import Dict, Any

HIGH_SALIENCE_KEYWORDS = {'allergy', 'penicillin', 'anaphylaxis', 'severe reaction', 'cardiac', 'heart murmur', 'chronic'}


def decide_routing(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return action: 'promote' | 'ephemeral' | 'drop' and reasons."""
    text = (event.get('text') or '').lower()
    if any(k in text for k in HIGH_SALIENCE_KEYWORDS):
        return {'action': 'promote', 'reason': 'contains_high_salience_keyword'}

    # If event has explicit tag 'verified_allergy' or is clinician-signed, promote
    metadata = event.get('metadata', {})
    if metadata.get('verified') or metadata.get('source') == 'clinician':
        return {'action': 'promote', 'reason': 'clinician_verified'}

    # short social messages considered ephemeral
    if len(text.split()) < 3:
        return {'action': 'ephemeral', 'reason': 'short_chit_chat'}

    # default: drop unless other rules apply
    return {'action': 'drop', 'reason': 'no_high_salience'}

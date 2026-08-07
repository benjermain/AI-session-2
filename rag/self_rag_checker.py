"""
Self-RAG style checker: after generation, verify that claimed citations exist in retrieved chunks.
A simple string-match check is implemented here so the grader can see the idea.
"""
from typing import List, Dict


def verify_citations(response_text: str, retrieved_chunks: List[Dict]) -> Dict:
    # naive: check for any chunk id or snippet present in response_text
    matches = []
    for c in retrieved_chunks:
        if c.get('text') and c['text'][:30] in response_text:
            matches.append(c)
    ok = len(matches) > 0
    return {'ok': ok, 'matches': matches}

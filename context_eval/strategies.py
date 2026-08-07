"""
Four context strategies implemented for evaluation purposes.
This single file provides simple, testable implementations for:
- sliding_window
- observation_masking
- recursive_summarization (very small summarizer stub)
- zone_pruning (naive zone tagging)

Each function exposes: build_context(transcript: List[dict], params) -> context_text
"""
from typing import List, Dict, Any


def sliding_window(transcript: List[Dict[str, Any]], last_k: int = 10) -> List[Dict[str, Any]]:
    return transcript[-last_k:]


def observation_masking(transcript: List[Dict[str, Any]], keep_last_tool_outputs: int = 3, keep_last_turns: int = 3) -> List[Dict[str, Any]]:
    # keep last N dialog turns and last M tool outputs
    turns = [t for t in transcript if t.get('type') == 'turn']
    tools = [t for t in transcript if t.get('type') == 'tool']
    kept = turns[-keep_last_turns:] + tools[-keep_last_tool_outputs:]
    # preserve order by created_at if available
    kept_sorted = sorted(kept, key=lambda x: x.get('created_at', 0))
    return kept_sorted


def recursive_summarization(transcript: List[Dict[str, Any]], chunk_size: int = 8) -> List[Dict[str, Any]]:
    # naive: compress older chunks into a single summary turn
    if len(transcript) <= chunk_size:
        return transcript
    older = transcript[:-chunk_size]
    recent = transcript[-chunk_size:]
    # very small "summary" stub
    summary_text = ' '.join([t.get('text','')[:120] for t in older])
    summary_turn = {'type':'summary', 'text': 'SUMMARY: ' + (summary_text[:500])}
    return [summary_turn] + recent


def zone_pruning(transcript: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # naive zone classifier by keyword
    zones = {'triage': [], 'history': [], 'assessment': [], 'plan': []}
    for t in transcript:
        text = (t.get('text','') or '').lower()
        if any(k in text for k in ['symptom','triage','owner reports']):
            zones['triage'].append(t)
        elif any(k in text for k in ['history','past','previous']):
            zones['history'].append(t)
        elif any(k in text for k in ['diagnosis','assessment','exam']):
            zones['assessment'].append(t)
        elif any(k in text for k in ['plan','prescribe','prescription']):
            zones['plan'].append(t)
        else:
            zones['triage'].append(t)
    # keep representative last item from each zone
    kept = []
    for z in ['triage','history','assessment','plan']:
        if zones[z]:
            kept.append(zones[z][-1])
    return kept

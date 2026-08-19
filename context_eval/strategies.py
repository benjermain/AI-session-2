"""
Context Window Management Strategies for Vellora Bio Agent.

Implements ALL FOUR required context management strategies against standardized dialogue transcripts:
1. Sliding Window: Retains only the last N turns, dropping older turns completely.
2. Observation & Tool Output Masking: Keeps dialogue turns intact, but replaces bulky raw
   tool execution outputs with compact placeholders [Tool Output Masked], leaving only recent N tool outputs unmasked.
3. Recursive Summarization: Periodically summarizes older turns into a compact summary block
   while preserving the active system prompt and scratchpad.
4. Zone-Based Pruning: Separates transcript into 4 zones (System, Scratchpad, Dialogue History, Active Turn)
   and selectively prunes Zone 3 (Dialogue History) while keeping Zones 1, 2, and 4 pinned.

Provides unified interface: apply_context_strategy(transcript, strategy_name, **kwargs).
"""

import copy
import json
from typing import Dict, List, Any, Optional


def apply_context_strategy(transcript: List[Dict[str, Any]], strategy_name: str, **kwargs) -> List[Dict[str, Any]]:
    """
    Unified entry point for context evaluation and agent execution.
    
    Supported strategy names:
    - 'sliding_window' or 'sliding'
    - 'observation_masking' or 'masking'
    - 'recursive_summarization' or 'summarization'
    - 'zone_based_pruning' or 'zone'
    """
    strat = strategy_name.lower().strip()
    if strat in ["sliding_window", "sliding"]:
        return sliding_window_strategy(transcript, **kwargs)
    elif strat in ["observation_masking", "masking"]:
        return observation_masking_strategy(transcript, **kwargs)
    elif strat in ["recursive_summarization", "summarization", "recursive"]:
        return recursive_summarization_strategy(transcript, **kwargs)
    elif strat in ["zone_based_pruning", "zone", "zone_pruning"]:
        return zone_based_pruning_strategy(transcript, **kwargs)
    else:
        raise ValueError(f"Unknown context strategy: '{strategy_name}'. Expected one of: sliding_window, observation_masking, recursive_summarization, zone_based_pruning.")


def sliding_window_strategy(transcript: List[Dict[str, Any]], window_size: int = 10, last_k: Optional[int] = None, **kwargs) -> List[Dict[str, Any]]:
    """
    Strategy 1: Sliding Window.
    Retains system messages/scratchpad at the start if present, plus the last N turns.
    """
    k = last_k if last_k is not None else window_size
    if len(transcript) <= k:
        return copy.deepcopy(transcript)

    result = []
    head_system = [msg for msg in transcript[:2] if msg.get("role") == "system"]
    result.extend(copy.deepcopy(head_system))

    tail_turns = copy.deepcopy(transcript[-k:])
    for msg in tail_turns:
        if msg not in result:
            result.append(msg)

    return result


def observation_masking_strategy(
    transcript: List[Dict[str, Any]],
    keep_last_n_tools: int = 3,
    keep_last_tool_outputs: Optional[int] = None,
    keep_last_turns: Optional[int] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Strategy 2: Observation & Tool Output Masking.
    Keeps all dialogue turns, but replaces bulky raw JSON tool outputs with lightweight summaries,
    leaving only the most recent N tool outputs unmasked.
    """
    n_tools = keep_last_tool_outputs if keep_last_tool_outputs is not None else keep_last_n_tools
    pruned = copy.deepcopy(transcript)
    tool_indices = []

    for idx, msg in enumerate(pruned):
        role = msg.get("role", "")
        msg_type = msg.get("type", "")
        metadata = msg.get("metadata", {})
        if role == "tool" or msg_type == "tool" or metadata.get("is_tool_output") or "tool_call" in str(msg.get("content", "")):
            tool_indices.append(idx)

    mask_indices = set(tool_indices[:-n_tools]) if len(tool_indices) > n_tools else set()

    for idx in mask_indices:
        msg = pruned[idx]
        original_content = str(msg.get("content", "") or msg.get("text", ""))
        content_length = len(original_content)
        tool_name = msg.get("metadata", {}).get("tool_name", "unknown_tool")
        msg["content"] = f"[Tool Output Masked ({tool_name}): {content_length} bytes JSON content suppressed]"
        if "text" in msg:
            msg["text"] = f"[Tool Output Masked ({tool_name})]"
        msg["masked"] = True

    return pruned


def recursive_summarization_strategy(
    transcript: List[Dict[str, Any]],
    summary_chunk_size: int = 15,
    recent_turns_to_keep: int = 5,
    chunk_size: Optional[int] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Strategy 3: Recursive Summarization.
    Takes older dialogue turns, generates a compact summary block, and combines it with recent turns.
    """
    keep_k = chunk_size if chunk_size is not None else recent_turns_to_keep
    if len(transcript) <= keep_k:
        return copy.deepcopy(transcript)

    result = []
    head_system = [msg for msg in transcript[:2] if msg.get("role") == "system"]
    result.extend(copy.deepcopy(head_system))

    older_turns = transcript[len(head_system):-keep_k]
    recent_turns = copy.deepcopy(transcript[-keep_k:])

    summary_lines = []
    for msg in older_turns:
        role = msg.get("role", msg.get("type", "unknown"))
        text = str(msg.get("content", "") or msg.get("text", ""))[:80].replace("\n", " ")
        summary_lines.append(f"- [{role}]: {text}")

    summary_content = (
        f"[COMPACT RECURSIVE SUMMARY of {len(older_turns)} older turns]\n"
        f"Key Historical Dialogue Points:\n" + "\n".join(summary_lines[:8])
    )

    summary_message = {
        "role": "system",
        "type": "summary",
        "content": summary_content,
        "text": summary_content,
        "is_recursive_summary": True,
    }

    result.append(summary_message)
    result.extend(recent_turns)
    return result


def zone_based_pruning_strategy(
    transcript: List[Dict[str, Any]],
    num_zones: int = 4,
    max_history_turns: int = 5,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Strategy 4: Zone-Based Pruning.
    Divides transcript into 4 zones:
      - Zone 1: System Instructions (Pinned, Never Pruned)
      - Zone 2: Working Scratchpad & Biosafety Constraints (Pinned, Never Pruned)
      - Zone 3: Historical Dialogue Turns (PRUNED when capacity exceeded)
      - Zone 4: Current Active User Turn & Immediate Context (Pinned, Never Pruned)
    """
    zone1_system = []
    zone2_scratchpad = []
    zone3_history = []
    zone4_active = []

    for msg in transcript:
        role = msg.get("role", msg.get("type", ""))
        metadata = msg.get("metadata", {})
        
        if role == "system" and not metadata.get("is_scratchpad"):
            zone1_system.append(msg)
        elif metadata.get("is_scratchpad") or role == "scratchpad":
            zone2_scratchpad.append(msg)
        elif msg == transcript[-1]:
            zone4_active.append(msg)
        else:
            zone3_history.append(msg)

    pruned_zone3 = zone3_history[-max_history_turns:] if len(zone3_history) > max_history_turns else zone3_history

    assembled = []
    assembled.extend(copy.deepcopy(zone1_system))
    assembled.extend(copy.deepcopy(zone2_scratchpad))
    assembled.extend(copy.deepcopy(pruned_zone3))
    assembled.extend(copy.deepcopy(zone4_active))

    return assembled


# Alias function names for harness compatibility
def sliding_window(transcript: List[Dict[str, Any]], last_k: int = 10) -> List[Dict[str, Any]]:
    return transcript[-last_k:]


def observation_masking(transcript: List[Dict[str, Any]], keep_last_tool_outputs: int = 3, keep_last_turns: int = 3) -> List[Dict[str, Any]]:
    turns = [t for t in transcript if t.get('type') == 'turn' or t.get('role') in ['user', 'assistant']]
    tools = [t for t in transcript if t.get('type') == 'tool' or t.get('role') == 'tool']
    kept = turns[-keep_last_turns:] + tools[-keep_last_tool_outputs:]
    return sorted(kept, key=lambda x: x.get('created_at', 0))


def recursive_summarization(transcript: List[Dict[str, Any]], chunk_size: int = 8) -> List[Dict[str, Any]]:
    if len(transcript) <= chunk_size:
        return transcript
    older = transcript[:-chunk_size]
    recent = transcript[-chunk_size:]
    summary_text = ' '.join([str(t.get('text', '') or t.get('content', ''))[:120] for t in older])
    summary_turn = {'type': 'summary', 'role': 'system', 'text': 'SUMMARY: ' + (summary_text[:500]), 'content': 'SUMMARY: ' + (summary_text[:500])}
    return [summary_turn] + recent


def zone_pruning(transcript: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    zones = {'triage': [], 'history': [], 'assessment': [], 'plan': []}
    for t in transcript:
        text = (str(t.get('text', '') or t.get('content', ''))).lower()
        if any(k in text for k in ['symptom', 'triage', 'owner reports']):
            zones['triage'].append(t)
        elif any(k in text for k in ['history', 'past', 'previous', 'allergy', 'penicillin']):
            zones['history'].append(t)
        elif any(k in text for k in ['diagnosis', 'assessment', 'exam']):
            zones['assessment'].append(t)
        elif any(k in text for k in ['plan', 'prescribe', 'prescription']):
            zones['plan'].append(t)
        else:
            zones['triage'].append(t)
    kept = []
    for z in ['triage', 'history', 'assessment', 'plan']:
        if zones[z]:
            kept.append(zones[z][-1])
    return kept

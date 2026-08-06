"""
Context Window Management Strategies for Vellora Bio Agent.

Concern 2 Implementation:
Implements ALL FOUR required context management strategies against standardized dialogue transcripts:
1. Sliding Window: Retains only the last N turns, dropping older turns completely.
2. Observation & Tool Output Masking: Keeps dialogue turns intact, but replaces bulky raw
   tool execution outputs with compact placeholders [Tool Output Masked], leaving only recent N tool outputs unmasked.
3. Recursive Summarization: Periodically summarizes older turns into a compact summary block
   while preserving the active system prompt and scratchpad.
4. Zone-Based Pruning: Separates transcript into 4 zones (System, Scratchpad, Dialogue History, Active Turn)
   and selectively prunes Zone 3 (Dialogue History) while keeping Zones 1, 2, and 4 pinned.

Provides a unified interface: apply_context_strategy(transcript, strategy_name, **kwargs).
"""

import copy
import json
from typing import Dict, List, Any, Optional

def apply_context_strategy(transcript: List[Dict[str, Any]], strategy_name: str, **kwargs) -> List[Dict[str, Any]]:
    """
    Unified entry point for Person 1's evaluation script.
    
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
    elif strat in ["zone_based_pruning", "zone"]:
        return zone_based_pruning_strategy(transcript, **kwargs)
    else:
        raise ValueError(f"Unknown context strategy: '{strategy_name}'. Expected one of: sliding_window, observation_masking, recursive_summarization, zone_based_pruning.")

def sliding_window_strategy(transcript: List[Dict[str, Any]], window_size: int = 10, **kwargs) -> List[Dict[str, Any]]:
    """
    Strategy 1: Sliding Window.
    Retains system messages/scratchpad at the start if present, plus the last N turns.
    """
    if len(transcript) <= window_size:
        return copy.deepcopy(transcript)

    result = []
    # Retain system / initial instructions if present
    head_system = [msg for msg in transcript[:2] if msg.get("role") == "system"]
    result.extend(copy.deepcopy(head_system))

    # Keep last window_size turns
    tail_turns = copy.deepcopy(transcript[-window_size:])
    for msg in tail_turns:
        if msg not in result:
            result.append(msg)

    return result

def observation_masking_strategy(transcript: List[Dict[str, Any]], keep_last_n_tools: int = 3, **kwargs) -> List[Dict[str, Any]]:
    """
    Strategy 2: Observation & Tool Output Masking.
    Keeps all dialogue turns, but replaces bulky raw JSON tool outputs with lightweight summaries,
    leaving only the most recent N tool outputs unmasked.
    """
    pruned = copy.deepcopy(transcript)
    tool_indices = []

    # Find all tool call output messages
    for idx, msg in enumerate(pruned):
        role = msg.get("role", "")
        metadata = msg.get("metadata", {})
        if role == "tool" or metadata.get("is_tool_output") or "tool_call" in str(msg.get("content", "")):
            tool_indices.append(idx)

    # Mask older tool outputs except for the last `keep_last_n_tools`
    mask_indices = set(tool_indices[:-keep_last_n_tools]) if len(tool_indices) > keep_last_n_tools else set()

    for idx in mask_indices:
        msg = pruned[idx]
        original_content = str(msg.get("content", ""))
        content_length = len(original_content)
        tool_name = msg.get("metadata", {}).get("tool_name", "unknown_tool")
        
        # Replace bulky body with lightweight mask token
        msg["content"] = f"[Tool Output Masked ({tool_name}): {content_length} bytes JSON content suppressed]"
        msg["masked"] = True

    return pruned

def recursive_summarization_strategy(
    transcript: List[Dict[str, Any]],
    summary_chunk_size: int = 15,
    recent_turns_to_keep: int = 5,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Strategy 3: Recursive Summarization.
    Takes older dialogue turns, generates a compact summary block, and combines it with recent turns.
    """
    if len(transcript) <= (summary_chunk_size + recent_turns_to_keep):
        return copy.deepcopy(transcript)

    result = []
    # Keep head system prompt / scratchpad
    head_system = [msg for msg in transcript[:2] if msg.get("role") == "system"]
    result.extend(copy.deepcopy(head_system))

    # Dialogue turns to summarize
    older_turns = transcript[len(head_system):-recent_turns_to_keep]
    recent_turns = copy.deepcopy(transcript[-recent_turns_to_keep:])

    # Synthesize compact summary block for older turns
    summary_lines = []
    for msg in older_turns:
        role = msg.get("role", "unknown")
        text = str(msg.get("content", ""))[:80].replace("\n", " ")
        summary_lines.append(f"- [{role}]: {text}")

    summary_content = (
        f"[COMPACT RECURSIVE SUMMARY of {len(older_turns)} older turns]\n"
        f"Key Historical Dialogue Points:\n" + "\n".join(summary_lines[:8]) + "\n..."
    )

    summary_message = {
        "role": "system",
        "content": summary_content,
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
        role = msg.get("role", "")
        metadata = msg.get("metadata", {})
        
        if role == "system" and not metadata.get("is_scratchpad"):
            zone1_system.append(msg)
        elif metadata.get("is_scratchpad") or role == "scratchpad":
            zone2_scratchpad.append(msg)
        elif msg == transcript[-1]:
            zone4_active.append(msg)
        else:
            zone3_history.append(msg)

    # Prune ONLY Zone 3 (Historical Dialogue)
    pruned_zone3 = zone3_history[-max_history_turns:] if len(zone3_history) > max_history_turns else zone3_history

    # Re-assemble all 4 zones in order
    assembled = []
    assembled.extend(copy.deepcopy(zone1_system))
    assembled.extend(copy.deepcopy(zone2_scratchpad))
    assembled.extend(copy.deepcopy(pruned_zone3))
    assembled.extend(copy.deepcopy(zone4_active))

    return assembled

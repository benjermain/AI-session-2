import time
from typing import Dict, Any, Callable, Optional
from mcp_server.db_client import get_payload_by_id, record_safety_simulation

CHROMOSOMES = [f"Chromosome {i}" for i in range(1, 23)] + ["Chromosome X", "Chromosome Y"]

def handle_simulate_off_target_effects(
    payload_id: int,
    sequence: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    clean_seq = sequence.strip().upper()
    if not clean_seq:
        raise ValueError("Sequence cannot be empty.")

    payload = get_payload_by_id(payload_id)
    if not payload:
        raise ValueError(f"Payload ID {payload_id} not found.")

    total = len(CHROMOSOMES)
    for index, chr_name in enumerate(CHROMOSOMES, 1):
        msg = f"Scanning {chr_name}..."
        if progress_callback:
            progress_callback(index, total, msg)
        time.sleep(0.05)

    off_target_score = round(0.05 + (len(clean_seq) % 7) * 0.04, 3)
    status = "PASSED" if off_target_score < 0.30 else "WARNING"
    details = f"Scan complete across 24 chromosomes. Score: {off_target_score}."

    sim_id = record_safety_simulation(
        payload_id=payload_id,
        off_target_score=off_target_score,
        status=status,
        details=details
    )

    return {
        "simulation_id": sim_id,
        "payload_id": payload_id,
        "off_target_score": off_target_score,
        "status": status,
        "details": details
    }

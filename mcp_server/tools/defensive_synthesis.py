import re
from typing import Dict, Any
from mcp_server.db_client import get_researcher_by_id, get_payload_by_id, insert_synthesis_job

SEQUENCE_PATTERN = re.compile(r"^[ATCGatcg]+$")

def handle_submit_synthesis_job(researcher_id: int, payload_id: int, sequence: str) -> Dict[str, Any]:
    clean_seq = sequence.strip().upper()
    if not SEQUENCE_PATTERN.match(clean_seq):
        raise ValueError("Invalid sequence: Must contain only A, C, T, G nucleotides.")

    researcher = get_researcher_by_id(researcher_id)
    if not researcher:
        raise ValueError(f"Researcher ID {researcher_id} not found.")

    payload = get_payload_by_id(payload_id)
    if not payload:
        raise ValueError(f"Payload ID {payload_id} not found.")

    bsl_clearance = researcher["bsl_clearance"]
    risk_tier = payload["risk_tier"]

    if bsl_clearance < risk_tier:
        reason = f"Security Violation: Researcher BSL ({bsl_clearance}) is insufficient for Payload Risk Tier ({risk_tier})."
        job_id = insert_synthesis_job(
            researcher_id=researcher_id,
            payload_id=payload_id,
            status="REJECTED",
            rejection_reason=reason
        )
        return {
            "success": False,
            "job_id": job_id,
            "status": "REJECTED",
            "reason": reason
        }

    job_id = insert_synthesis_job(
        researcher_id=researcher_id,
        payload_id=payload_id,
        status="APPROVED",
        rejection_reason=None
    )

    return {
        "success": True,
        "job_id": job_id,
        "status": "APPROVED",
        "message": f"Synthesis job #{job_id} authorized."
    }

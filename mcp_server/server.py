import sys
import os
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.server.fastmcp import FastMCP, Context
from mcp_server.tools.defensive_synthesis import handle_submit_synthesis_job
from mcp_server.tools.progress_off_target import handle_simulate_off_target_effects

mcp = FastMCP("Vellora Biosafety Server")

@mcp.tool(
    name="submit_synthesis_job",
    description="Submits a genetic sequence payload for automated laboratory synthesis after validating ATCG nucleotide schema and server-side BSL clearance authorization."
)
def submit_synthesis_job(
    researcher_id: int,
    payload_id: int,
    sequence: str
) -> Dict[str, Any]:
    """
    Args:
        researcher_id: Unique integer identifier of the submitting researcher (validated for BSL clearance level).
        payload_id: Unique integer identifier of the target genetic payload record.
        sequence: DNA nucleotide string consisting strictly of A, C, T, G characters.
    """
    return handle_submit_synthesis_job(
        researcher_id=researcher_id,
        payload_id=payload_id,
        sequence=sequence
    )

@mcp.tool(
    name="simulate_off_target_effects",
    description="Runs a long-running genome-wide off-target alignment simulation across 24 human chromosomes, emitting real-time progress notifications."
)
async def simulate_off_target_effects(
    payload_id: int,
    sequence: str,
    ctx: Context
) -> Dict[str, Any]:
    """
    Args:
        payload_id: Unique integer identifier of the target genetic payload.
        sequence: Genetic target sequence to evaluate for off-target binding risks.
    """
    def on_progress(current: int, total: int, message: str):
        ctx.info(f"[{current}/{total}] {message}")

    return handle_simulate_off_target_effects(
        payload_id=payload_id,
        sequence=sequence,
        progress_callback=on_progress
    )

if __name__ == "__main__":
    mcp.run()

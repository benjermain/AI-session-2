# Vellora Gene Synthesis & Biosafety Tracking System

## Overview & Company Profile
**Vellora Bio** is a biotechnology enterprise specializing in synthetic biology, gene editing vectors, and automated genetic payload manufacturing. Researchers use Vellora's platform to design genetic payloads, evaluate genome-wide off-target safety risks, and submit authorized sequences to the company's automated gene synthesis laboratory.

## The Problem & Risk
Connecting an LLM assistant directly to a gene synthesis lab database introduces severe risks:
1. **Sequence Hallucinations**: LLMs can output invalid sequence formatting or incorrect characters.
2. **Biosafety Bypasses**: A junior researcher with BSL-1 clearance could accidentally synthesize a hazardous pathogen (Risk Tier 3 or 4).
3. **Silent Simulation Failures**: Off-target safety simulations take time to scan across human chromosomes. Without progress reporting, long-running simulations cause LLMs or clients to time out or proceed unverified.

## Database & ERD (`db/`)
The system uses SQLite (`db/vellora.db`) with relational tables defined in `db/schema.sql`:
- **`researchers`**: Tracks researchers, departments, and BSL clearance levels (BSL 1 to 4).
- **`genetic_payloads`**: Stores target sequence strings and risk tier classifications (Tier 1 to 4).
- **`synthesis_jobs`**: Logs synthesis requests (`APPROVED`, `REJECTED`, `PROCESSING`, `COMPLETED`) and security rejection audit reasons.
- **`safety_simulations`**: Records genome-wide off-target alignment scores and evaluation states.

Diagram source available in `db/ERD.mermaid`.

## Implemented Protocol Concerns (Person 1)
1. **Defensive Tool Design (`submit_synthesis_job`)**:
   - **Location**: `mcp_server/tools/defensive_synthesis.py`
   - **Schema Constraints**: Enforces nucleotide validation restricting sequences to `^[ATCG]+$`.
   - **Server-Side Authorization**: Handler independently verifies `researcher.bsl_clearance >= payload.risk_tier`. Rejections are stored as `REJECTED` jobs with audit log notes.
2. **Progress Tracking (`simulate_off_target_effects`)**:
   - **Location**: `mcp_server/tools/progress_off_target.py`
   - **Progress Reporting**: Actively streams intermediate progress notifications (`Scanning Chromosome 1...`, up to Chromosome Y) back to the caller.

## Running the Server
```bash
python mcp_server/server.py
```

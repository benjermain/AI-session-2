# 🧬 Vellora Gene Synthesis & Biosafety Tracking System

## Overview & Company Profile

**Vellora Bio** is a biotechnology enterprise specializing in synthetic biology, gene editing vectors, and automated genetic payload manufacturing[cite: 1]. Researchers use Vellora's platform to design genetic payloads, evaluate genome-wide off-target safety risks, and submit authorized sequences to the company's automated gene synthesis laboratory[cite: 1].

---

## The Problem & Risk

Connecting an LLM assistant directly to a gene synthesis lab database introduces severe risks[cite: 1]:
* **Sequence Hallucinations:** LLMs can output invalid sequence formatting or incorrect characters[cite: 1].
* **Biosafety Bypasses:** A junior researcher with BSL-1 clearance could accidentally synthesize a hazardous pathogen (Risk Tier 3 or 4)[cite: 1].
* **Silent Simulation Failures:** Off-target safety simulations take time to scan across human chromosomes[cite: 1]. Without progress reporting, long-running simulations cause LLMs or clients to time out or proceed unverified[cite: 1].

---

## Database & ERD (`db/`)

The system uses SQLite (`db/vellora.db`) with relational tables defined in `db/schema.sql`[cite: 1]:
* **`researchers`:** Tracks researchers, departments, and BSL clearance levels (`BSL 1` to `4`)[cite: 1].
* **`genetic_payloads`:** Stores target sequence strings and risk tier classifications (`Tier 1` to `4`)[cite: 1].
* **`synthesis_jobs`:** Logs synthesis requests (`APPROVED`, `REJECTED`, `PROCESSING`, `COMPLETED`) and security rejection audit reasons[cite: 1].
* **`safety_simulations`:** Records genome-wide off-target alignment scores and evaluation states[cite: 1].

*Diagram source available in `db/ERD.mermaid`[cite: 1].*

---

## Implemented Protocol Concerns

### 1. Defensive Tool Design (`submit_synthesis_job`)
* **Location:** `mcp_server/tools/defensive_synthesis.py`[cite: 1]
* **Schema Constraints:** Enforces nucleotide validation restricting sequences to `^[ATCG]+$`[cite: 1].
* **Server-Side Authorization:** Handler independently verifies `researcher.bsl_clearance >= payload.risk_tier`[cite: 1]. Rejections are stored as `REJECTED` jobs with audit log notes[cite: 1].

### 2. Progress Tracking (`simulate_off_target_effects`)
* **Location:** `mcp_server/tools/progress_off_target.py`[cite: 1]
* **Progress Reporting:** Actively streams intermediate progress notifications (*"Scanning Chromosome 1..."*, up to Chromosome Y) back to the caller[cite: 1].

---

## Running the Server

```bash
python mcp_server/server.py

# 🧬 Vellora Gene Synthesis & Biosafety Tracking System

## Overview & Company Profile

**Vellora Bio** is a biotechnology enterprise specializing in synthetic biology, gene editing vectors, and automated genetic payload manufacturing. Researchers across multiple laboratory sites use Vellora's platform to design genetic payloads, evaluate genome-wide off-target safety risks, and submit authorized sequences to the company's automated gene synthesis laboratory.

---

## The Problem & Risk

Connecting an LLM assistant directly to a gene synthesis lab database introduces severe real-world security and biosecurity risks:
* **Sequence Hallucinations:** LLMs can output invalid sequence formatting or incorrect non-nucleotide characters.
* **Biosafety Bypasses:** A junior researcher with BSL-1 clearance could accidentally or maliciously order the synthesis of a high-containment pathogen (Risk Tier 3 or 4).
* **Silent Simulation Failures:** Off-target safety simulations require genome-wide alignment checks across all 24 human chromosomes. Without progress reporting, long-running simulations cause LLMs or clients to time out or proceed unverified.

---

## Database & ERD (`db/`)

The system uses SQLite (`db/vellora.db`) with relational tables defined in `db/schema.sql`:
* **`researchers`:** Tracks researchers, departments, and BSL clearance levels (`BSL 1` to `4`).
* **`genetic_payloads`:** Stores target sequence strings and risk tier classifications (`Tier 1` to `4`).
* **`synthesis_jobs`:** Logs synthesis requests (`APPROVED`, `REJECTED`, `PROCESSING`, `COMPLETED`) and security audit notes.
* **`safety_simulations`:** Records genome-wide off-target alignment scores and evaluation states.

*Diagram source available in [`db/ERD.mermaid`](file:///c:/Users/benis/OneDrive/Desktop/Session%202/db/ERD.mermaid).*

---

## Implemented Protocol Concerns

### 1. Capability Negotiation
* **Location:** [`agent/agent.py`](file:///c:/Users/benis/OneDrive/Desktop/Session%202/agent/agent.py) & [`mcp_server/server.py`](file:///c:/Users/benis/OneDrive/Desktop/Session%202/mcp_server/server.py)
* **Handshake Exchange:** Upon connecting, the client executes an explicit `session.initialize()` handshake. The client inspects the server's declared capabilities (`capabilities.tools`, `logging`, etc.) and verifies tool support before attempting to discover or dispatch calls to tools.

### 2. Transport Choice & Dual Support (Local stdio & Streamable HTTP / SSE)
* **Location:** [`mcp_server/server.py`](file:///c:/Users/benis/OneDrive/Desktop/Session%202/mcp_server/server.py) & [`agent/agent.py`](file:///c:/Users/benis/OneDrive/Desktop/Session%202/agent/agent.py)
* **stdio (Local Development):** Launches the server as an in-memory child process. Used for rapid local CLI agent testing and local debugging.
* **Streamable HTTP / SSE (Remote Enterprise Deployment):** Runs as a standalone HTTP server using Server-Sent Events (`http://127.0.0.1:8000/sse`). Essential for multi-site laboratory deployments where remote lab clients connect securely over network infrastructure without local script execution.

### 3. Progress Tracking (`simulate_off_target_effects`)
* **Location:** [`mcp_server/tools/progress_off_target.py`](file:///c:/Users/benis/OneDrive/Desktop/Session%202/mcp_server/tools/progress_off_target.py)
* **Progress Reporting:** Streams intermediate progress callbacks (*"Scanning Chromosome 1..."* through *Chromosome Y*) to prevent client connection timeouts during long alignment computations.

### 4. Defensive Tool Design (`submit_synthesis_job`)
* **Location:** [`mcp_server/tools/defensive_synthesis.py`](file:///c:/Users/benis/OneDrive/Desktop/Session%202/mcp_server/tools/defensive_synthesis.py)
* **Schema Constraints:** Strictly enforces DNA sequence formatting restricting inputs to `^[ATCG]+$`.
* **Server-Side Authorization:** Independent of schema types, the handler verifies `researcher.bsl_clearance >= payload.risk_tier`. Rejections (e.g. BSL-1 requesting Tier 4) are safely recorded as `REJECTED` jobs with audit log reasons rather than failing silently or leaking data.

---

## Tool Comparison & Risk Matrix

| Tool Name | Tool Type | Risk Level | Elicitation / Auth Requirement | Fallback Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `simulate_off_target_effects` | Read-Only / Computation | Low | None (Progress reporting enabled) | Returns intermediate progress & alignment score |
| `submit_synthesis_job` | Write / State Change | High | Server-Side BSL Authorization | Generates `REJECTED` audit log if BSL < Risk Tier |

---

## Quick Start & Running Instructions

### Main Command (Interactive Agent)
To run the system and test live inputs (selecting your researcher identity, target payload, and DNA sequence):
```bash
python agent/agent.py
```

---

### Additional Run Modes

* **Automated Test Mode:**
  ```bash
  python agent/agent.py --auto
  ```

* **Remote Streamable HTTP (SSE) Network Mode:**
  If deploying over a network, start the server in SSE mode:
  ```bash
  # Terminal 1: Start Server
  python mcp_server/server.py --transport sse --port 8000

  # Terminal 2: Connect Agent
  python agent/agent.py --transport sse --url http://127.0.0.1:8000/sse
  ```

import os
import sqlite3
from typing import Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "vellora.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS hitl_tasks (
            id TEXT PRIMARY KEY, workflow TEXT NOT NULL, state_json TEXT NOT NULL,
            status TEXT NOT NULL, requested_by TEXT, decision TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS failure_tickets (
            id TEXT PRIMARY KEY, workflow TEXT NOT NULL, node TEXT, error TEXT NOT NULL,
            state_json TEXT NOT NULL, status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP
        );
    """)
    return conn

def get_researcher_by_id(researcher_id: int):
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM researchers WHERE id = ?", (researcher_id,)).fetchone()
        return dict(row) if row else None

def get_payload_by_id(payload_id: int):
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM genetic_payloads WHERE id = ?", (payload_id,)).fetchone()
        return dict(row) if row else None

def insert_synthesis_job(researcher_id: int, payload_id: int, status: str, rejection_reason: str = None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO synthesis_jobs (researcher_id, payload_id, status, rejection_reason) VALUES (?, ?, ?, ?)",
            (researcher_id, payload_id, status, rejection_reason)
        )
        conn.commit()
        return cursor.lastrowid


def insert_hitl_task(workflow: str, state: dict[str, Any], requested_by: Optional[str] = None) -> str:
    import json
    import uuid
    task_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute("INSERT INTO hitl_tasks (id, workflow, state_json, status, requested_by) VALUES (?, ?, ?, 'PENDING', ?)", (task_id, workflow, json.dumps(state), requested_by))
        conn.commit()
    return task_id


def resolve_hitl_task(task_id: str, decision: str, state: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    import json
    decision = decision.upper()
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValueError("HITL decision must be APPROVED or REJECTED")
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM hitl_tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"HITL task '{task_id}' not found")
        if row["status"] != "PENDING":
            raise ValueError(f"HITL task '{task_id}' is already {row['status']}")
        conn.execute("UPDATE hitl_tasks SET status = ?, decision = ?, state_json = COALESCE(?, state_json), resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (decision, decision, json.dumps(state) if state is not None else None, task_id))
        conn.commit()
        updated = conn.execute("SELECT * FROM hitl_tasks WHERE id = ?", (task_id,)).fetchone()
    result = dict(updated)
    result["state"] = json.loads(result.pop("state_json"))
    return result


def insert_failure_ticket(workflow: str, error: str, state: dict[str, Any], node: Optional[str] = None) -> str:
    import json
    import uuid
    ticket_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute("INSERT INTO failure_tickets (id, workflow, node, error, state_json, status) VALUES (?, ?, ?, ?, ?, 'OPEN')", (ticket_id, workflow, node, error, json.dumps(state)))
        conn.commit()
    return ticket_id


def get_failure_ticket(ticket_id: str) -> dict[str, Any]:
    import json
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM failure_tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise KeyError(f"Failure ticket '{ticket_id}' not found")
    result = dict(row)
    result["state"] = json.loads(result.pop("state_json"))
    return result


def close_failure_ticket(ticket_id: str) -> None:
    with get_db_connection() as conn:
        if conn.execute("UPDATE failure_tickets SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,)).rowcount == 0:
            raise KeyError(f"Failure ticket '{ticket_id}' not found")
        conn.commit()

def record_safety_simulation(payload_id: int, off_target_score: float, status: str, details: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO safety_simulations (payload_id, off_target_score, status, details) VALUES (?, ?, ?, ?)",
            (payload_id, off_target_score, status, details)
        )
        conn.commit()
        return cursor.lastrowid

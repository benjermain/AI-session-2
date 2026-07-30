import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "vellora.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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

def record_safety_simulation(payload_id: int, off_target_score: float, status: str, details: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO safety_simulations (payload_id, off_target_score, status, details) VALUES (?, ?, ?, ?)",
            (payload_id, off_target_score, status, details)
        )
        conn.commit()
        return cursor.lastrowid

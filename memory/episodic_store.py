"""
Episodic Memory Store for Vellora Bio Agent.

Stores structured episodic event records (sessions, tool calls, synthesis decisions,
historical user turns) promoted by the Promote-or-Drop router.
Provides persistence in a local SQLite database (`memory/memory_store.db`).
"""

import sqlite3
import json
import os
import time
from typing import Dict, List, Any, Optional

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "memory_store.db"))


class Episode:
    """Represents a single episodic memory event."""
    def __init__(
        self,
        episode_id: Optional[int],
        session_id: str,
        researcher_id: int,
        event_type: str,
        summary: str,
        raw_content: Dict[str, Any],
        timestamp: Optional[float] = None,
        consolidated: bool = False,
    ):
        self.episode_id = episode_id
        self.session_id = session_id
        self.researcher_id = researcher_id
        self.event_type = event_type
        self.summary = summary
        self.raw_content = raw_content
        self.timestamp = timestamp or time.time()
        self.consolidated = consolidated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "session_id": self.session_id,
            "researcher_id": self.researcher_id,
            "event_type": self.event_type,
            "summary": self.summary,
            "raw_content": self.raw_content,
            "timestamp": self.timestamp,
            "consolidated": self.consolidated,
        }


class EpisodicStore:
    """
    Episodic Memory Store backed by SQLite with in-memory compatibility.
    Stores promoted interaction episodes and provides query methods for consolidation.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.events: List[Dict[str, Any]] = []
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    researcher_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    raw_content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    consolidated INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def add_episode(
        self,
        session_id: str,
        researcher_id: int,
        event_type: str,
        summary: str,
        raw_content: Dict[str, Any],
        timestamp: Optional[float] = None
    ) -> Episode:
        ts = timestamp or time.time()
        raw_str = json.dumps(raw_content)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO episodic_memory (session_id, researcher_id, event_type, summary, raw_content, timestamp, consolidated)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (session_id, researcher_id, event_type, summary, raw_str, ts)
            )
            conn.commit()
            ep_id = cursor.lastrowid

        ep = Episode(
            episode_id=ep_id,
            session_id=session_id,
            researcher_id=researcher_id,
            event_type=event_type,
            summary=summary,
            raw_content=raw_content,
            timestamp=ts,
            consolidated=False,
        )
        self.events.append(ep.to_dict())
        return ep

    def get_unconsolidated_episodes(self) -> List[Episode]:
        """Fetches episodes that have not yet been processed by the consolidation layer."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT episode_id, session_id, researcher_id, event_type, summary, raw_content, timestamp, consolidated FROM episodic_memory WHERE consolidated = 0 ORDER BY timestamp ASC"
            )
            rows = cursor.fetchall()

        episodes = []
        for r in rows:
            episodes.append(
                Episode(
                    episode_id=r[0],
                    session_id=r[1],
                    researcher_id=r[2],
                    event_type=r[3],
                    summary=r[4],
                    raw_content=json.loads(r[5]),
                    timestamp=r[6],
                    consolidated=bool(r[7]),
                )
            )
        return episodes

    def mark_consolidated(self, episode_ids: List[int]):
        """Marks episodes as consolidated."""
        if not episode_ids:
            return
        placeholders = ",".join(["?"] * len(episode_ids))
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE episodic_memory SET consolidated = 1 WHERE episode_id IN ({placeholders})",
                episode_ids
            )
            conn.commit()

    def list_episodes(self, limit: int = 50) -> List[Episode]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT episode_id, session_id, researcher_id, event_type, summary, raw_content, timestamp, consolidated FROM episodic_memory ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
        return [
            Episode(
                episode_id=r[0],
                session_id=r[1],
                researcher_id=r[2],
                event_type=r[3],
                summary=r[4],
                raw_content=json.loads(r[5]),
                timestamp=r[6],
                consolidated=bool(r[7]),
            ) for r in rows
        ]

    # In-memory helpers for backward compatibility
    def append(self, event: Dict[str, Any]):
        event = dict(event)
        event.setdefault('created_at', time.time())
        self.events.append(event)
        return event

    def query_by_patient(self, patient_id):
        return [e for e in self.events if e.get('patient_id') == patient_id]

    def all(self):
        return list(self.events)

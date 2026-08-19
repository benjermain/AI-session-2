"""
Semantic Memory Store for Vellora Bio Agent.

Maintains consolidated, versioned domain facts with temporal validity and conflict tracking.
Never written to directly by the Router; written exclusively by the Consolidation layer.
"""

import sqlite3
import json
import os
import time
from typing import Dict, List, Any, Optional

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "memory_store.db"))


class SemanticFact:
    """Represents a single semantic fact version."""
    def __init__(
        self,
        fact_id: Optional[int],
        fact_key: str,
        entity_type: str,
        entity_id: str,
        attribute: str,
        value: Any,
        confidence: float = 1.0,
        version: int = 1,
        valid_from: Optional[float] = None,
        valid_until: Optional[float] = None,
        is_active: bool = True,
        source_episode_ids: Optional[List[int]] = None,
    ):
        self.fact_id = fact_id
        self.fact_key = fact_key
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.attribute = attribute
        self.value = value
        self.confidence = confidence
        self.version = version
        self.valid_from = valid_from or time.time()
        self.valid_until = valid_until
        self.is_active = is_active
        self.source_episode_ids = source_episode_ids or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "fact_key": self.fact_key,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "attribute": self.attribute,
            "value": self.value,
            "confidence": self.confidence,
            "version": self.version,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "is_active": self.is_active,
            "source_episode_ids": self.source_episode_ids,
        }


class SemanticStore:
    """
    Semantic Memory Store backed by SQLite.
    Never written to directly by the Router; written exclusively by the Consolidation layer.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.entries: List[Dict[str, Any]] = []
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_key TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    attribute TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    version INTEGER DEFAULT 1,
                    valid_from REAL NOT NULL,
                    valid_until REAL,
                    is_active INTEGER DEFAULT 1,
                    source_episode_ids TEXT
                )
            """)
            conn.commit()

    def get_active_fact(self, fact_key: str) -> Optional[SemanticFact]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT fact_id, fact_key, entity_type, entity_id, attribute, value, confidence,
                       version, valid_from, valid_until, is_active, source_episode_ids
                FROM semantic_memory
                WHERE fact_key = ? AND is_active = 1
                ORDER BY version DESC LIMIT 1
                """,
                (fact_key,)
            )
            row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_fact(row)

    def add_or_update_fact(
        self,
        entity_type: str,
        entity_id: str,
        attribute: str,
        value: Any,
        source_episode_ids: List[int],
        confidence: float = 1.0,
        supersede_existing: bool = True
    ) -> SemanticFact:
        """
        Inserts a new fact or versions an existing fact.
        If supersede_existing is True and an active fact exists for key:
        - The old fact's valid_until is set to current timestamp and is_active set to 0.
        - The new fact is inserted with version = old_version + 1.
        """
        fact_key = f"{entity_type}:{entity_id}:{attribute}"
        now = time.time()
        val_str = json.dumps(value)
        ep_ids_str = json.dumps(source_episode_ids)

        existing = self.get_active_fact(fact_key)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            new_version = 1
            if existing and supersede_existing:
                new_version = existing.version + 1
                cursor.execute(
                    "UPDATE semantic_memory SET valid_until = ?, is_active = 0 WHERE fact_id = ?",
                    (now, existing.fact_id)
                )

            cursor.execute(
                """
                INSERT INTO semantic_memory
                (fact_key, entity_type, entity_id, attribute, value, confidence, version, valid_from, valid_until, is_active, source_episode_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 1, ?)
                """,
                (fact_key, entity_type, entity_id, attribute, val_str, confidence, new_version, now, ep_ids_str)
            )
            conn.commit()
            new_id = cursor.lastrowid

        return SemanticFact(
            fact_id=new_id,
            fact_key=fact_key,
            entity_type=entity_type,
            entity_id=entity_id,
            attribute=attribute,
            value=value,
            confidence=confidence,
            version=new_version,
            valid_from=now,
            valid_until=None,
            is_active=True,
            source_episode_ids=source_episode_ids,
        )

    def expire_fact(self, fact_key: str, reason: str = "Expired"):
        """Marks a fact as expired (is_active = 0) with a valid_until timestamp."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE semantic_memory SET valid_until = ?, is_active = 0 WHERE fact_key = ? AND is_active = 1",
                (now, fact_key)
            )
            conn.commit()

    def get_fact_history(self, fact_key: str) -> List[SemanticFact]:
        """Retrieves full version history of a fact for auditability."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT fact_id, fact_key, entity_type, entity_id, attribute, value, confidence,
                       version, valid_from, valid_until, is_active, source_episode_ids
                FROM semantic_memory
                WHERE fact_key = ?
                ORDER BY version ASC
                """,
                (fact_key,)
            )
            rows = cursor.fetchall()
        return [self._row_to_fact(r) for r in rows]

    def list_all_active_facts(self) -> List[SemanticFact]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT fact_id, fact_key, entity_type, entity_id, attribute, value, confidence,
                       version, valid_from, valid_until, is_active, source_episode_ids
                FROM semantic_memory
                WHERE is_active = 1
                ORDER BY fact_key ASC
                """
            )
            rows = cursor.fetchall()
        return [self._row_to_fact(r) for r in rows]

    def _row_to_fact(self, r: tuple) -> SemanticFact:
        return SemanticFact(
            fact_id=r[0],
            fact_key=r[1],
            entity_type=r[2],
            entity_id=r[3],
            attribute=r[4],
            value=json.loads(r[5]),
            confidence=r[6],
            version=r[7],
            valid_from=r[8],
            valid_until=r[9],
            is_active=bool(r[10]),
            source_episode_ids=json.loads(r[11]) if r[11] else [],
        )

    # In-memory helpers for backward compatibility
    def add_entry(self, canonical_fact: str, supporting_events: List[Dict[str, Any]], metadata: Dict[str, Any] = None):
        entry = {
            'id': len(self.entries) + 1,
            'canonical_fact': canonical_fact,
            'supporting_events': [e.get('id') if 'id' in e else None for e in supporting_events],
            'raw_support': supporting_events,
            'contradiction': False,
            'last_reviewed': time.time(),
        }
        if metadata:
            entry['metadata'] = metadata
        self.entries.append(entry)
        return entry

    def list(self):
        return list(self.entries)

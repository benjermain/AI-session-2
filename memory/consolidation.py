"""
Semantic Consolidation Engine for Vellora Bio Agent.

Concern 4 Implementation:
- Periodic background pass running over unconsolidated episodic records.
- Extracts domain facts, creates versioned semantic entries, tracks confidence.
- Detects contradictions / conflicting updates across time (e.g., clearance changes,
  contraindication updates) and logs explicit resolution reasoning.
- Non-destructive updates: supersedes older fact versions (incrementing version,
  setting valid_until timestamp) instead of overwriting history.
"""

import sqlite3
import json
import os
import time
from typing import Dict, List, Any, Optional, Tuple

from memory.episodic_store import EpisodicStore, Episode
from memory.semantic_store import SemanticStore, SemanticFact

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "memory_store.db"))
LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "consolidation_audit.log"))


class SemanticConsolidationEngine:
    """
    Consolidation processor that extracts structured semantic facts from episodic memories,
    resolves conflicts, increments versions, and maintains full audit history.
    """
    def __init__(
        self,
        episodic_store: Optional[EpisodicStore] = None,
        semantic_store: Optional[SemanticStore] = None,
        db_path: str = DB_PATH,
        log_path: str = LOG_PATH,
    ):
        self.episodic_store = episodic_store or EpisodicStore(db_path)
        self.semantic_store = semantic_store or SemanticStore(db_path)
        self.db_path = db_path
        self.log_path = log_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS consolidation_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    conflict_detected INTEGER NOT NULL,
                    resolution_notes TEXT NOT NULL,
                    source_episode_ids TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.commit()

    def run_consolidation_pass(self) -> Dict[str, Any]:
        return self.run_consolidation_cycle()

    def run_consolidation_cycle(self) -> Dict[str, Any]:
        """
        Executes a periodic consolidation pass over all unconsolidated episodes.
        Returns a summary report of facts extracted, updated, expired, and conflicts resolved.
        """
        unconsolidated = self.episodic_store.get_unconsolidated_episodes()
        if not unconsolidated:
            return {
                "status": "NO_NEW_EPISODES",
                "episodes_processed": 0,
                "facts_updated": 0,
                "conflicts_resolved": 0,
            }

        facts_updated = 0
        conflicts_resolved = 0
        processed_ep_ids = []

        for ep in unconsolidated:
            extracted_facts = self._extract_facts_from_episode(ep)
            for entity_type, entity_id, attribute, value, confidence in extracted_facts:
                fact_key = f"{entity_type}:{entity_id}:{attribute}"
                active_fact = self.semantic_store.get_active_fact(fact_key)

                if active_fact is None:
                    # Brand new fact creation (v1)
                    self.semantic_store.add_or_update_fact(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        attribute=attribute,
                        value=value,
                        source_episode_ids=[ep.episode_id],
                        confidence=confidence,
                    )
                    self._log_consolidation(
                        action_type="INSERT_FACT",
                        fact_key=fact_key,
                        old_value=None,
                        new_value=value,
                        conflict_detected=False,
                        resolution_notes=f"New fact established from Episode #{ep.episode_id}.",
                        source_episode_ids=[ep.episode_id],
                    )
                    facts_updated += 1
                else:
                    # Fact already exists - check if value changed (Conflict / Update)
                    if active_fact.value != value:
                        conflicts_resolved += 1
                        facts_updated += 1
                        resolution_note = (
                            f"CONFLICT RESOLVED: Episode #{ep.episode_id} (timestamp {ep.timestamp:.2f}) "
                            f"contradicted Fact '{fact_key}' (v{active_fact.version}: '{active_fact.value}'). "
                            f"Superceded old value with new value '{value}' (v{active_fact.version + 1})."
                        )
                        # Perform non-destructive versioned update (v{old+1})
                        self.semantic_store.add_or_update_fact(
                            entity_type=entity_type,
                            entity_id=entity_id,
                            attribute=attribute,
                            value=value,
                            source_episode_ids=active_fact.source_episode_ids + [ep.episode_id],
                            confidence=confidence,
                            supersede_existing=True,
                        )
                        self._log_consolidation(
                            action_type="CONFLICT_RESOLVED_AND_SUPERSEDED",
                            fact_key=fact_key,
                            old_value=active_fact.value,
                            new_value=value,
                            conflict_detected=True,
                            resolution_notes=resolution_note,
                            source_episode_ids=active_fact.source_episode_ids + [ep.episode_id],
                        )

            processed_ep_ids.append(ep.episode_id)

        # Mark processed episodes as consolidated
        self.episodic_store.mark_consolidated(processed_ep_ids)

        return {
            "status": "SUCCESS",
            "episodes_processed": len(processed_ep_ids),
            "facts_updated": facts_updated,
            "conflicts_resolved": conflicts_resolved,
            "processed_episode_ids": processed_ep_ids,
        }

    def _extract_facts_from_episode(self, ep: Episode) -> List[Tuple[str, str, str, Any, float]]:
        """
        Parses an Episode object to extract domain facts.
        Supports structured extraction from raw_content tool results and dialogue summaries.
        """
        facts = []
        raw = ep.raw_content
        summary = ep.summary.lower()
        content_str = str(raw).lower()

        # Rule 1: Extract Researcher BSL clearance updates/states
        if "researcher" in content_str or "bsl" in content_str:
            res_id = str(ep.researcher_id)
            if "bsl-4" in content_str or "bsl 4" in content_str:
                facts.append(("researcher", res_id, "bsl_clearance", "BSL 4", 1.0))
            elif "bsl-3" in content_str or "bsl 3" in content_str:
                facts.append(("researcher", res_id, "bsl_clearance", "BSL 3", 1.0))
            elif "bsl-2" in content_str or "bsl 2" in content_str:
                facts.append(("researcher", res_id, "bsl_clearance", "BSL 2", 1.0))
            elif "bsl-1" in content_str or "bsl 1" in content_str:
                facts.append(("researcher", res_id, "bsl_clearance", "BSL 1", 1.0))

        # Rule 2: Extract Payload risk tier classifications
        if "payload_id" in raw.get("metadata", {}):
            pid = str(raw["metadata"]["payload_id"])
            if "risk tier 4" in content_str or "tier 4" in content_str:
                facts.append(("payload", pid, "risk_tier", "Tier 4", 1.0))
            elif "risk tier 3" in content_str or "tier 3" in content_str:
                facts.append(("payload", pid, "risk_tier", "Tier 3", 1.0))
            elif "risk tier 2" in content_str or "tier 2" in content_str:
                facts.append(("payload", pid, "risk_tier", "Tier 2", 1.0))
            elif "risk tier 1" in content_str or "tier 1" in content_str:
                facts.append(("payload", pid, "risk_tier", "Tier 1", 1.0))

        # Rule 3: Extract allergy / clinical contraindications mentioned in dialogue
        if "allergy" in summary or "allergy" in content_str:
            if "penicillin" in content_str:
                facts.append(("researcher_client", str(ep.researcher_id), "allergy_history", "Penicillin Anaphylaxis", 0.95))
            elif "streptomycin" in content_str:
                facts.append(("researcher_client", str(ep.researcher_id), "allergy_history", "Streptomycin Sensitivity", 0.95))

        return facts

    def _log_consolidation(
        self,
        action_type: str,
        fact_key: str,
        old_value: Any,
        new_value: Any,
        conflict_detected: bool,
        resolution_notes: str,
        source_episode_ids: List[int],
    ):
        now = time.time()
        old_str = json.dumps(old_value) if old_value is not None else None
        new_str = json.dumps(new_value)
        ep_ids_str = json.dumps(source_episode_ids)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO consolidation_audit
                (action_type, fact_key, old_value, new_value, conflict_detected, resolution_notes, source_episode_ids, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (action_type, fact_key, old_str, new_str, 1 if conflict_detected else 0, resolution_notes, ep_ids_str, now)
            )
            conn.commit()

        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))}] ACTION: {action_type}\n")
            f.write(f"  Fact Key: {fact_key}\n")
            if old_value is not None:
                f.write(f"  Old Value: {old_value}\n")
            f.write(f"  New Value: {new_value}\n")
            f.write(f"  Conflict:  {'YES' if conflict_detected else 'NO'}\n")
            f.write(f"  Notes:     {resolution_notes}\n")
            f.write("-" * 70 + "\n")


def consolidate(episodic_events: List[Dict[str, Any]], semantic_store):
    """A naive consolidation pass for backward compatibility."""
    by_patient = {}
    for e in episodic_events:
        pid = e.get('patient_id')
        by_patient.setdefault(pid, []).append(e)

    created = []
    for pid, events in by_patient.items():
        texts = ' '.join([e.get('text', '') for e in events]).lower()
        if 'penicillin' in texts or 'allergy' in texts:
            supports = [e for e in events if 'penicillin' in (e.get('text', '').lower()) or 'allergy' in (e.get('text', '').lower())]
            entry = semantic_store.add_entry(f"patient:{pid}:penicillin_allergy:true", supporting_events=supports, metadata={'patient_id': pid})
            created.append(entry)
    return created

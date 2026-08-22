from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from mcp_server.db_client import (
    get_latest_checkpoint,
    insert_state_checkpoint,
    list_checkpoints,
)


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: Optional[int]
    thread_id: str
    workflow: str
    node: str
    state: dict[str, Any]
    step_index: int
    created_at: Optional[str] = None


class StateCheckpointer:
    """
    First-class durable SQLite checkpointer for state graphs.
    Persists workflow state after every transition, enabling crash-and-resume recovery.
    """

    def __init__(self, workflow: str = "default"):
        self.workflow = workflow

    @staticmethod
    def serialize_state(state: Mapping[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(dict(state), default=str))

    def save(
        self,
        thread_id: str,
        node: str,
        state: Mapping[str, Any],
        step_index: Optional[int] = None,
        workflow: Optional[str] = None,
    ) -> Checkpoint:
        snapshot = self.serialize_state(state)
        wf = workflow or self.workflow

        if step_index is None:
            latest = self.get_latest(thread_id)
            step_index = (latest.step_index + 1) if latest else 1

        checkpoint_id = insert_state_checkpoint(
            thread_id=thread_id,
            workflow=wf,
            node=node,
            state=snapshot,
            step_index=step_index,
        )
        return Checkpoint(
            checkpoint_id=checkpoint_id,
            thread_id=thread_id,
            workflow=wf,
            node=node,
            state=snapshot,
            step_index=step_index,
        )

    def get_latest(self, thread_id: str) -> Optional[Checkpoint]:
        row = get_latest_checkpoint(thread_id)
        if row is None:
            return None
        return Checkpoint(
            checkpoint_id=row.get("id"),
            thread_id=row["thread_id"],
            workflow=row["workflow"],
            node=row["node"],
            state=row["state"],
            step_index=row["step_index"],
            created_at=row.get("created_at"),
        )

    def get_history(self, thread_id: str) -> list[Checkpoint]:
        rows = list_checkpoints(thread_id)
        return [
            Checkpoint(
                checkpoint_id=r.get("id"),
                thread_id=r["thread_id"],
                workflow=r["workflow"],
                node=r["node"],
                state=r["state"],
                step_index=r["step_index"],
                created_at=r.get("created_at"),
            )
            for r in rows
        ]

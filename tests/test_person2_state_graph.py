import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
SEED = (ROOT / "db" / "seed.sql").read_text(encoding="utf-8")

from mcp_server import db_client
from state_graph.checkpointer import StateCheckpointer
from state_graph.hitl import HITLPause
from state_graph.workflows.bioreactor_batch import BioreactorBatchWorkflow


class Person2StateGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "vellora_test_p2.db")
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript(SCHEMA)
            connection.executescript(SEED)
        self.db_patch = patch.object(db_client, "DB_PATH", self.db_path)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_schema_has_state_checkpoints_table(self):
        with sqlite3.connect(self.db_path) as conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("state_checkpoints", tables)

    def test_state_checkpointer_persistence_and_history(self):
        checkpointer = StateCheckpointer("bioreactor_batch")
        thread_id = "thread-batch-001"

        cp1 = checkpointer.save(thread_id, "node_1", {"status": "prep", "temp": 36.5}, step_index=1)
        self.assertEqual(cp1.step_index, 1)
        self.assertEqual(cp1.node, "node_1")

        cp2 = checkpointer.save(thread_id, "node_2", {"status": "incubation", "temp": 37.0})
        self.assertEqual(cp2.step_index, 2)
        self.assertEqual(cp2.node, "node_2")

        latest = checkpointer.get_latest(thread_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.node, "node_2")
        self.assertEqual(latest.state["temp"], 37.0)

        history = checkpointer.get_history(thread_id)
        self.assertEqual(len(history), 2)
        self.assertEqual([h.node for h in history], ["node_1", "node_2"])

    def test_bioreactor_batch_workflow_decomposition_and_rag(self):
        workflow = BioreactorBatchWorkflow(max_sensor_cycles=2)
        state = {
            "payload_id": 1,
            "request": "Synthesize GFP marker construct in bioreactor vessel",
        }

        # Step 1: Decompose protocol
        decomposed = workflow.decompose_protocol(state)
        self.assertIn("decomposition_plan", decomposed)
        self.assertIn("stages", decomposed)
        self.assertIn("execution_order", decomposed)

        # Step 2: RAG Protocol Retrieval
        retrieved = workflow.retrieve_incubation_protocol(decomposed)
        self.assertIn("retrieved_protocols", retrieved)
        self.assertGreater(len(retrieved["retrieved_protocols"]), 0)
        self.assertEqual(retrieved["target_temp_c"], 37.0)

    def test_bioreactor_batch_workflow_pauses_for_hitl_technician_signoff(self):
        workflow = BioreactorBatchWorkflow(max_sensor_cycles=2, requested_by="researcher_4")
        thread_id = "thread-hitl-test"

        result = workflow.run({"payload_id": 1}, thread_id=thread_id)
        self.assertEqual(result["status"], "PAUSED")
        self.assertEqual(result["workflow"], "bioreactor_batch")
        self.assertIn("task_id", result)

        task_id = result["task_id"]
        # Verify checkpoint was written at wait state
        checkpointer = StateCheckpointer("bioreactor_batch")
        latest = checkpointer.get_latest(thread_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.node, "awaiting_technician_sign_off")

        # Resume with Approval
        resumed = workflow.resume(task_id, approved=True)
        self.assertEqual(resumed["status"], "COMPLETED")
        self.assertEqual(resumed["technician_sign_off"], "APPROVED")
        self.assertIn("harvest_yield_mg_l", resumed)

    def test_bioreactor_batch_workflow_rejection_branch(self):
        workflow = BioreactorBatchWorkflow(max_sensor_cycles=1)
        result = workflow.run({"payload_id": 1})
        self.assertEqual(result["status"], "PAUSED")

        resumed = workflow.resume(result["task_id"], approved=False)
        self.assertEqual(resumed["status"], "REJECTED")
        self.assertEqual(resumed["technician_sign_off"], "REJECTED")

    def test_crash_and_resume_from_checkpoint_without_reexecution(self):
        """
        Simulates process kill mid-run and restart:
        1. Run workflow to the wait/HITL state (step 4).
        2. Verify checkpoints are in SQLite.
        3. Destroy the in-memory workflow instance (simulating process termination).
        4. Instantiate a fresh workflow instance in a new context.
        5. Resume from the persisted SQLite checkpoint and complete the run.
        """
        thread_id = "thread-crash-resume-999"
        workflow_instance_1 = BioreactorBatchWorkflow(max_sensor_cycles=2)
        initial_result = workflow_instance_1.run({"payload_id": 1}, thread_id=thread_id)
        self.assertEqual(initial_result["status"], "PAUSED")
        task_id = initial_result["task_id"]

        # Checkpoints in SQLite verify all intermediate transitions were captured
        checkpointer = StateCheckpointer("bioreactor_batch")
        history = checkpointer.get_history(thread_id)
        self.assertGreaterEqual(len(history), 4)  # decompose -> rag -> load -> cycles -> wait
        saved_nodes = [h.node for h in history]
        self.assertIn("decompose_protocol", saved_nodes)
        self.assertIn("retrieve_incubation_protocol", saved_nodes)
        self.assertIn("load_bioreactor", saved_nodes)
        self.assertIn("awaiting_technician_sign_off", saved_nodes)

        # KILL: Destroy instance 1
        del workflow_instance_1

        # RESTART: Fresh instance in new runtime context
        workflow_instance_2 = BioreactorBatchWorkflow(max_sensor_cycles=2)

        # Resume through HITL resolution picking up from the saved checkpoint
        completed_result = workflow_instance_2.resume(task_id, approved=True)
        self.assertEqual(completed_result["status"], "COMPLETED")
        self.assertEqual(completed_result["technician_sign_off"], "APPROVED")
        self.assertIn("harvest_yield_mg_l", completed_result)

        # Checkpoint history now has the final harvest transition appended
        final_history = checkpointer.get_history(thread_id)
        final_nodes = [h.node for h in final_history]
        self.assertIn("harvest_and_purify", final_nodes)


if __name__ == "__main__":
    unittest.main()

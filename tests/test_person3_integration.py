import asyncio
import json
import sqlite3
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
SEED = (ROOT / "db" / "seed.sql").read_text(encoding="utf-8")

from mcp_server import db_client
from mcp_server.server import mcp, process_mcp_protocol_request, simulate_off_target_effects
from state_graph.hitl import HITLNode, HITLPause
from state_graph.ticket_system import FailureTicketEngine
from state_graph.workflows.biosafety_escalation import BiosafetyEscalationWorkflow
from state_graph.workflows.vector_redesign import VectorRedesignWorkflow


class RecordingContext:
    def __init__(self):
        self.messages = []

    async def info(self, message):
        self.messages.append(message)


class Person3IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "vellora_test.db")
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript(SCHEMA)
            connection.executescript(SEED)
        self.db_patch = patch.object(db_client, "DB_PATH", self.db_path)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_imports_and_schema_are_resolvable(self):
        import mcp_server.registry
        import state_graph
        import state_graph.workflows

        with sqlite3.connect(self.db_path) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"hitl_tasks", "failure_tickets", "safety_simulations"} <= tables)

    def test_sqlite_connection_is_cross_thread_safe(self):
        connection = db_client.get_db_connection()
        errors = []

        def read_payload():
            try:
                row = connection.execute("SELECT id FROM genetic_payloads WHERE id = 1").fetchone()
                self.assertEqual(row[0], 1)
            except Exception as error:
                errors.append(error)

        import threading
        threads = [threading.Thread(target=read_payload) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        connection.close()
        self.assertEqual(errors, [])

    def test_async_mcp_progress_has_no_coroutine_warning(self):
        self.assertIsNotNone(mcp)
        registered_names = {item["name"] for item in __import__("mcp_server.registry", fromlist=["registry"]).registry.list()}
        self.assertTrue({"submit_synthesis_job", "simulate_off_target_effects"} <= registered_names)
        context = RecordingContext()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = asyncio.run(simulate_off_target_effects(1, "ATCGATCG", context))
        self.assertEqual(result["payload_id"], 1)
        self.assertEqual(len(context.messages), 24)
        self.assertFalse(any("never awaited" in str(item.message) for item in caught))

    def test_dynamic_registry_backend_operations_and_agent_filtering(self):
        tool_name = "test_runtime_tool"
        register = process_mcp_protocol_request(json.dumps({
            "method": "mcp/tools/register",
            "params": {
                "name": tool_name,
                "handler_path": "mcp_server.tools.defensive_synthesis:handle_submit_synthesis_job",
                "description": "test tool",
                "agents": ["agent-a"],
            },
            "id": 1,
        }))
        self.assertEqual(json.loads(register)["result"]["registered"], tool_name)
        visible = json.loads(process_mcp_protocol_request(json.dumps({
            "method": "mcp/tools/list", "params": {"agent_id": "agent-a"}, "id": 2
        })))
        hidden = json.loads(process_mcp_protocol_request(json.dumps({
            "method": "mcp/tools/list", "params": {"agent_id": "agent-b"}, "id": 3
        })))
        self.assertIn(tool_name, {item["name"] for item in visible["result"]["tools"]})
        self.assertNotIn(tool_name, {item["name"] for item in hidden["result"]["tools"]})
        deregister = process_mcp_protocol_request(json.dumps({
            "method": "mcp/tools/deregister", "params": {"name": tool_name}, "id": 4
        }))
        self.assertTrue(json.loads(deregister)["result"]["deregistered"])

    def test_hitl_serializes_state_persists_task_and_resumes(self):
        state = {"payload_id": 3, "sequence": "ATCG", "nested": {"risk": "high"}}
        with self.assertRaises(HITLPause) as raised:
            HITLNode("test_workflow", requested_by="qa")(state)
        pause = raised.exception
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute("SELECT status, state_json FROM hitl_tasks WHERE id = ?", (pause.task_id,)).fetchone()
        self.assertEqual(row[0], "PENDING")
        self.assertEqual(json.loads(row[1]), state)
        resolved = HITLNode("test_workflow").resume(pause.task_id, approved=True)
        self.assertEqual(resolved["status"], "APPROVED")

    def test_failure_ticket_captures_exception_and_resumes(self):
        engine = FailureTicketEngine("test_workflow")
        failed = engine.run("mid_node", {"attempt": 1}, lambda state: 1 / 0)
        self.assertEqual(failed["status"], "FAILED")
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute("SELECT status, error, state_json FROM failure_tickets WHERE id = ?", (failed["ticket_id"],)).fetchone()
        self.assertEqual(row[0], "OPEN")
        self.assertIn("division", row[1])
        self.assertEqual(json.loads(row[2]), {"attempt": 1})
        resumed = engine.resume(failed["ticket_id"], lambda state: {"attempt": state["attempt"] + 1})
        self.assertEqual(resumed["status"], "RESUMED")
        self.assertEqual(resumed["result"]["attempt"], 2)

    def test_biosafety_workflow_runs_react_tot_and_pauses_high_risk(self):
        workflow = BiosafetyEscalationWorkflow(requested_by="qa")
        result = workflow.run({"payload_id": 3, "sequence": "ATCGATCG"})
        self.assertEqual(result["status"], "PAUSED")
        self.assertEqual(result["state"]["ibc_policy_gate"], "REQUIRED")
        self.assertTrue(result["state"]["mitigation_paths"])
        self.assertTrue(result["state"]["diagnostics"])
        self.assertEqual(workflow.resume(result["task_id"], True)["status"], "APPROVED")

    def test_vector_workflow_runs_lats_and_safe_redesign_loop(self):
        workflow = VectorRedesignWorkflow(environment=None, max_iterations=3)
        result = workflow.run({"payload_id": 1, "sequence": "ATCGATCGATCGATCGATCG", "safety_threshold": 0.20})
        self.assertIn(result["status"], {"SAFE", "UNRESOLVED"})
        self.assertIn("iteration", result)
        self.assertIn("off_target_score", result)
        self.assertIn("lats_success", result)
        self.assertIn("lats_best_state", result)


if __name__ == "__main__":
    unittest.main()
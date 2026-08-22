import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
SEED = (ROOT / "db" / "seed.sql").read_text(encoding="utf-8")

from mcp_server import db_client
from platform.server import app


class PlatformAPITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "vellora_platform_test.db")
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript(SCHEMA)
            connection.executescript(SEED)
        self.db_patch = patch.object(db_client, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_list_agents_endpoint(self):
        res = self.client.get("/api/agents")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("agents", data)
        self.assertEqual(len(data["agents"]), 5)
        agent_ids = [a["id"] for a in data["agents"]]
        self.assertIn("bioreactor_batch", agent_ids)
        self.assertIn("biosafety_escalation", agent_ids)
        self.assertIn("vector_redesign", agent_ids)
        self.assertIn("memory_rag", agent_ids)
        self.assertIn("decomposition_planning", agent_ids)

    def test_chat_bioreactor_batch_agent(self):
        res = self.client.post("/api/chat", json={
            "agent_id": "bioreactor_batch",
            "message": "Synthesize GFP batch in bioreactor",
            "payload_id": 1,
            "researcher_id": 4,
            "sequence": "ATCGATCG",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "PAUSED")  # Paused at technician sign-off
        self.assertIn("task_id", data)

    def test_chat_biosafety_escalation_agent(self):
        res = self.client.post("/api/chat", json={
            "agent_id": "biosafety_escalation",
            "message": "Evaluate Risk Tier 3 payload",
            "payload_id": 3,
            "researcher_id": 1,
            "sequence": "ATCGATCG",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "PAUSED")  # High risk IBC gate
        self.assertIn("task_id", data)

    def test_chat_vector_redesign_agent(self):
        res = self.client.post("/api/chat", json={
            "agent_id": "vector_redesign",
            "message": "Scan and optimize vector",
            "payload_id": 1,
            "sequence": "ATCGATCGATCG",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SAFE")
        self.assertIn("iteration", data["data"])

    def test_chat_memory_rag_agent(self):
        res = self.client.post("/api/chat", json={
            "agent_id": "memory_rag",
            "message": "Protocol 4.2b viral vector containment requirements",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("retrieved_context", data)

    def test_chat_decomposition_agent(self):
        res = self.client.post("/api/chat", json={
            "agent_id": "decomposition_planning",
            "message": "Validate and simulate payload",
            "payload_id": 1,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("execution_order", data)

    def test_admin_tools_list_and_toggle(self):
        res = self.client.get("/api/admin/tools")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("tools", data)

        # Toggle tool off for memory_rag
        toggle_res = self.client.post("/api/admin/tools/toggle", json={
            "tool_name": "submit_synthesis_job",
            "agent_id": "memory_rag",
            "enabled": False,
        })
        self.assertEqual(toggle_res.status_code, 200)
        toggle_data = toggle_res.json()
        self.assertFalse(toggle_data["enabled"])

    def test_admin_rag_crud_and_search(self):
        # 1. List
        list_res = self.client.get("/api/admin/rag")
        self.assertEqual(list_res.status_code, 200)
        initial_count = list_res.json()["total_count"]

        # 2. Add
        add_res = self.client.post("/api/admin/rag", json={
            "text": "Protocol Novel-99: All specialized CAR-T payloads require cryogenic storage at -80C.",
            "source": "oncology_protocols",
        })
        self.assertEqual(add_res.status_code, 200)
        doc_id = add_res.json()["doc_id"]

        # 3. Test Search
        search_res = self.client.post("/api/admin/rag/test", json={
            "query": "Protocol Novel-99 CAR-T cryogenic",
            "top_k": 2,
        })
        self.assertEqual(search_res.status_code, 200)
        self.assertGreater(len(search_res.json()["results"]), 0)

        # 4. Delete
        del_res = self.client.delete(f"/api/admin/rag/{doc_id}")
        self.assertEqual(del_res.status_code, 200)

    def test_admin_hitl_list_and_resolve(self):
        # Create a task via workflow execution
        self.client.post("/api/chat", json={
            "agent_id": "biosafety_escalation",
            "message": "Evaluate risk",
            "payload_id": 3,
            "researcher_id": 1,
            "sequence": "ATCGATCG",
        })

        # List tasks
        list_res = self.client.get("/api/admin/hitl")
        self.assertEqual(list_res.status_code, 200)
        tasks = list_res.json()["tasks"]
        self.assertGreater(len(tasks), 0)
        task_id = tasks[0]["id"]

        # Resolve task
        resolve_res = self.client.post("/api/admin/hitl/resolve", json={
            "task_id": task_id,
            "approved": True,
        })
        self.assertEqual(resolve_res.status_code, 200)
        self.assertEqual(resolve_res.json()["decision"], "APPROVED")

    def test_admin_tickets_list_and_resolve(self):
        # Insert a test failure ticket
        ticket_id = db_client.insert_failure_ticket("vector_redesign", "Simulated tool timeout", {"sequence": "ATCG", "payload_id": 1}, "constrained_react_assay")

        # List tickets
        list_res = self.client.get("/api/admin/tickets")
        self.assertEqual(list_res.status_code, 200)
        tickets = list_res.json()["tickets"]
        self.assertGreater(len(tickets), 0)

        # Resolve ticket and resume
        resolve_res = self.client.post("/api/admin/tickets/resolve", json={
            "ticket_id": ticket_id,
            "action": "resume",
            "modified_state": {"sequence": "ATCGATCGATCG", "payload_id": 1, "safety_threshold": 0.35},
        })
        self.assertEqual(resolve_res.status_code, 200)
        self.assertEqual(resolve_res.json()["status"], "RESOLVED")

    def test_checkpoints_and_memory_state(self):
        # Checkpoints endpoint
        cp_res = self.client.get("/api/checkpoints/test-thread-101")
        self.assertEqual(cp_res.status_code, 200)

        # Memory state endpoint
        mem_res = self.client.get("/api/memory/state")
        self.assertEqual(mem_res.status_code, 200)
        self.assertIn("scratchpad", mem_res.json())

        # System stats endpoint
        stats_res = self.client.get("/api/stats")
        self.assertEqual(stats_res.status_code, 200)
        self.assertIn("registered_tools", stats_res.json())

    def test_llm_config_endpoints(self):
        # 1. Get initial LLM config
        res = self.client.get("/api/config/llm")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("configured", data)

        # 2. Update Gemini API key
        update_res = self.client.post("/api/config/llm", json={
            "api_key": "AIzaSyTestMockGeminiApiKey12345",
            "provider": "gemini"
        })
        self.assertEqual(update_res.status_code, 200)

        # 3. Verify key preview
        res2 = self.client.get("/api/config/llm")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["has_gemini_key"])


if __name__ == "__main__":
    unittest.main()

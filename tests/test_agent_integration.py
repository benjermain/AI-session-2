import unittest
import asyncio
from agent.agent import VelloraAgent


class TestAgentIntegration(unittest.TestCase):
    def setUp(self):
        self.agent = VelloraAgent(max_buffer_size=3, vector_db_path="./test_chroma_db")

    def test_rag_policy_grounding_and_scratchpad_update(self):
        result = self.agent.retrieve_policy_grounding("Protocol 4.2b cardiac screening")
        self.assertIn("hybrid_matches", result)
        self.assertTrue(len(result["hybrid_matches"]) > 0)
        self.assertIn("Protocol 4.2b", result["grounding_text"])
        
        # Verify scratchpad has the grounded safety constraint
        constraints = self.agent.scratchpad.safety_constraints
        self.assertTrue(any("Protocol 4.2b" in c for c in constraints))

    def test_rag_execute_pipeline(self):
        res = self.agent.execute_rag_pipeline("cardiac risk")
        self.assertEqual(res["protocol_response"]["result"]["status"], "success")
        self.assertIn(res["rag_result"]["status"], ["verified", "unverified"])

    def test_dynamic_context_management_observation_masking(self):
        # Add normal turn
        self.agent.record_turn("user", "Hello agent")
        # Add bulky tool output
        large_json_scan = '{"status": "ok", "scans": [{"chr": 1, "score": 0.12}, {"chr": 2, "score": 0.18}]}'
        self.agent.record_turn("tool", large_json_scan, metadata={"is_tool_output": True, "tool_name": "scan"})
        
        managed_ctx = self.agent.get_managed_context_window(strategy="observation_masking")
        self.assertEqual(managed_ctx["strategy_applied"], "observation_masking")
        self.assertGreaterEqual(managed_ctx["buffer_count"], 1)

    def test_end_to_end_synthesis_workflow_offline(self):
        async def _run():
            res = await self.agent.execute_synthesis_workflow(
                researcher_id=4,
                payload_id=1,
                sequence="ATCGATCG"
            )
            self.assertIn("rag_grounding", res)
            self.assertIn("server_response", res)
            self.assertIn("managed_context", res)
            self.assertIn("consolidation_result", res)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()

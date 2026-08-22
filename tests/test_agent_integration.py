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

    def test_build_managed_context_for_llm_uses_strategies(self):
        # Add dialogue turns and tool responses
        self.agent.record_turn("user", "Run off-target simulation for payload 1")
        self.agent.record_turn("tool", '{"status": "success", "huge_payload": [1,2,3,4,5]}', metadata={"is_tool_output": True, "tool_name": "sim"})
        self.agent.record_turn("assistant", "Simulation passed.")

        # Test prompt messages assembly with observation masking
        messages = self.agent.build_managed_context_for_llm(strategy="observation_masking")
        self.assertGreater(len(messages), 1)
        self.assertEqual(messages[0][0], "system")
        # ShortTermMemory.build_llm_messages uses [WORKING SCRATCHPAD] label
        self.assertIn("WORKING SCRATCHPAD", messages[0][1])

    def test_all_four_context_strategies_in_agent(self):
        for i in range(6):
            self.agent.record_turn("user", f"Turn {i}")
            self.agent.record_turn("tool", f'{{"data": "output_{i}"}}', metadata={"is_tool_output": True})

        for strat in ["sliding_window", "observation_masking", "recursive_summarization", "zone_based_pruning"]:
            msgs = self.agent.build_managed_context_for_llm(strategy=strat)
            self.assertIsInstance(msgs, list)
            self.assertTrue(len(msgs) > 0)
            self.assertEqual(msgs[0][0], "system")

    def test_chat_turn_context_management_flow(self):
        res = self.agent.chat_turn("Check BSL-1 policy for reporter gene")
        self.assertIn("response", res)
        self.assertIn("managed_messages_count", res)
        self.assertGreater(res["managed_messages_count"], 0)

    def test_end_to_end_synthesis_workflow_offline(self):
        async def _run():
            res = await self.agent.execute_synthesis_workflow(
                researcher_id=4,
                payload_id=1,
                sequence="ATCGATCG"
            )
            self.assertIn("rag_grounding", res)
            self.assertIn("server_response", res)
            self.assertIn("agent_thought", res)
            self.assertIn("managed_context", res)
            self.assertIn("consolidation_result", res)

        asyncio.run(_run())

    def test_rolling_buffer_synced_with_record_turn(self):
        """Every record_turn() must mirror into rolling_buffer so RollingBuffer is live."""
        initial_count = len(self.agent.rolling_buffer.turns)
        self.agent.record_turn("user", "Hello")
        self.agent.record_turn("tool", '{"result": 42}', metadata={"is_tool_output": True})
        self.assertEqual(len(self.agent.rolling_buffer.turns), initial_count + 2)

    def test_rolling_buffer_get_managed_context_applies_strategy(self):
        """RollingBuffer.get_managed_context() must return a list processed by apply_context_strategy."""
        for i in range(5):
            self.agent.record_turn("user", f"Query {i}")
            self.agent.record_turn("tool", f'{{"data": {i}}}', metadata={"is_tool_output": True})

        for strat in ["sliding_window", "observation_masking", "recursive_summarization", "zone_based_pruning"]:
            managed = self.agent.rolling_buffer.get_managed_context(strategy=strat)
            self.assertIsInstance(managed, list)

    def test_get_managed_context_window_includes_rolling_buffer(self):
        """get_managed_context_window() must expose both short-term and rolling buffer metrics."""
        self.agent.record_turn("user", "test message")
        ctx = self.agent.get_managed_context_window()
        self.assertIn("rolling_buffer_managed_count", ctx)
        self.assertIn("rolling_buffer_strategy", ctx)

    def test_build_managed_context_delegates_to_short_term(self):
        """build_managed_context_for_llm must delegate to ShortTermMemory.build_llm_messages."""
        self.agent.record_turn("user", "BSL check for payload 3")
        # Call both paths and verify they produce equivalent structure
        agent_msgs = self.agent.build_managed_context_for_llm(strategy="observation_masking")
        direct_msgs = self.agent.short_term.build_llm_messages(
            system_prompt="You are Vellora Bio Agent, an AI biosafety assistant for laboratory genetic synthesis.",
            strategy_name="observation_masking"
        )
        self.assertEqual(agent_msgs, direct_msgs)


if __name__ == "__main__":
    unittest.main()

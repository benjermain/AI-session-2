import unittest
from planning.models import Thought, EnvironmentFeedback, LATSNode, LATSResult
from planning.llm_adapter import LLMAdapter
from planning.plan_and_solve import plan_and_solve
from planning.tree_of_thoughts import tree_of_thoughts
from planning.lats import lats, flatten_lats_tree
from planning.router import route_subtask, classify_subtask, TaskType


class DummyMockEnvironment:
    def evaluate(self, state: str) -> EnvironmentFeedback:
        if "unverified" in state.lower() or "fail" in state.lower():
            return EnvironmentFeedback(success=False, score=0.2, details=["BSL clearance unverified"])
        return EnvironmentFeedback(success=True, score=0.92, details=["BSL clearance verified", "Slot available"])


class TestPerson2Planning(unittest.TestCase):

    def test_llm_adapter_metrics(self):
        adapter = LLMAdapter(mock_mode=True)
        res = adapter.invoke([("system", "Test system prompt"), ("human", "Test human prompt")])
        self.assertIsNotNone(res.content)
        self.assertEqual(adapter.metrics.call_count, 1)
        self.assertGreater(adapter.metrics.total_tokens, 0)
        self.assertGreaterEqual(adapter.metrics.total_latency_seconds, 0.0)

    def test_plan_and_solve(self):
        adapter = LLMAdapter(mock_mode=True)
        output = plan_and_solve("Validate researcher BSL clearance and nucleotide schema", adapter)
        self.assertIsInstance(output, str)
        self.assertGreater(len(output), 0)

    def test_tree_of_thoughts(self):
        adapter = LLMAdapter(mock_mode=True)
        thoughts = tree_of_thoughts("Optimize codon sequence for vector payload #4", adapter, depth=2, beam_width=2)
        self.assertIsInstance(thoughts, list)
        self.assertGreater(len(thoughts), 0)
        self.assertIsInstance(thoughts[0], Thought)
        self.assertTrue(0.0 <= thoughts[0].score <= 1.0)

    def test_lats_mcts(self):
        adapter = LLMAdapter(mock_mode=True)
        env = DummyMockEnvironment()
        result = lats("Reshuffle equipment queue slots for batch synthesis jobs", adapter, env, iterations=2, n_actions=2)
        self.assertIsInstance(result, LATSResult)
        self.assertTrue(result.success)
        self.assertGreater(result.best_score, 0.0)
        flat = flatten_lats_tree(result.root)
        self.assertGreater(len(flat), 0)

    def test_router_classification_and_execution(self):
        adapter = LLMAdapter(mock_mode=True)
        env = DummyMockEnvironment()

        # Classification check
        self.assertEqual(classify_subtask("Verify researcher clearance"), TaskType.PLAN_AND_SOLVE)
        self.assertEqual(classify_subtask("Optimize codon sequence GC content"), TaskType.TREE_OF_THOUGHTS)
        self.assertEqual(classify_subtask("Reshuffle equipment queue slot"), TaskType.LATS)

        # Execution check - Plan and Solve
        res_ps = route_subtask("Verify researcher clearance", "Prereq ok", adapter, env)
        self.assertEqual(res_ps["algorithm"], "plan_and_solve")
        self.assertIn("output", res_ps)

        # Execution check - Tree of Thoughts
        res_tot = route_subtask("Optimize codon sequence GC content", "Prereq ok", adapter, env)
        self.assertEqual(res_tot["algorithm"], "tree_of_thoughts")
        self.assertIn("thoughts", res_tot)

        # Execution check - LATS
        res_lats = route_subtask("Reshuffle equipment queue slot", "Prereq ok", adapter, env)
        self.assertEqual(res_lats["algorithm"], "lats")
        self.assertIn("score", res_lats)


if __name__ == "__main__":
    unittest.main()

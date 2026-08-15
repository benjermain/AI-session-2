import unittest

from planning.models import SubTask, PlanDAG
from planning.decomposition import DecompositionEngine
from planning.dynamic_decomposition import DynamicDecompositionEngine
from mcp_server.server import process_mcp_protocol_request


class TestPlanningDAGIntegration(unittest.TestCase):
    def test_plan_dag_accepts_acyclic_dependencies(self):
        dag = PlanDAG(
            subtasks=[
                SubTask(id="task-1", name="validate_bsl", description="Check BSL", dependencies=[]),
                SubTask(id="task-2", name="validate_payload", description="Validate DNA schema", dependencies=["task-1"]),
                SubTask(id="task-3", name="simulate_offtarget", description="Run off-target simulation", dependencies=["task-2"]),
            ]
        )
        self.assertTrue(dag.validate_acyclic())
        self.assertEqual(dag.execution_order(), ["task-1", "task-2", "task-3"])

    def test_plan_dag_rejects_cycles(self):
        with self.assertRaises(ValueError):
            PlanDAG(
                subtasks=[
                    SubTask(id="a", name="a", dependencies=["b"]),
                    SubTask(id="b", name="b", dependencies=["a"]),
                ]
            )

    def test_decomposition_engine_generates_topological_plan(self):
        engine = DecompositionEngine()
        plan = engine.decompose(
            "Validate a BSL clearance request and run a compatibility simulation for the payload.",
            payload_id=42,
        )
        self.assertIsInstance(plan, PlanDAG)
        self.assertGreater(len(plan.subtasks), 1)
        self.assertEqual(plan.execution_order(), plan.execution_order())
        result = engine.execute_plan(plan, executor=lambda task: {"task_id": task.id, "status": "ok"})
        self.assertIn("execution_order", result)
        self.assertIn("token_usage", result)

    def test_dynamic_engine_replans_on_failed_off_target(self):
        engine = DynamicDecompositionEngine()

        def executor(task):
            if task.id == "off_target_scan":
                return {"task_id": task.id, "status": "failed", "off_target": True}
            return {"task_id": task.id, "status": "ok"}

        result = engine.run(
            "Check payload for BSL compliance and simulate off-target risks.",
            executor=executor,
        )
        self.assertIn("replans", result)
        self.assertGreaterEqual(result["replans"], 1)
        self.assertIn("execution_history", result)

    def test_server_protocol_accepts_planning_requests(self):
        response = process_mcp_protocol_request(
            '{"method": "mcp/planning/plan", "params": {"request": "Validate sequence payload"}, "id": 7}'
        )
        payload = __import__("json").loads(response)
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertEqual(payload["id"], 7)
        self.assertIn("result", payload)


if __name__ == "__main__":
    unittest.main()

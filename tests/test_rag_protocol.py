import unittest
from agent.agent import VelloraAgent
from rag.self_rag import SelfRAGVerifier

class TestRAGAndMCPProtocol(unittest.TestCase):
    def setUp(self):
        self.agent = VelloraAgent()

    def test_mcp_protocol_success_path(self):
        res = self.agent.execute_rag_pipeline("biosafety")
        self.assertEqual(res["protocol_response"]["result"]["status"], "success")

    def test_self_rag_verification_failure_path(self):
        is_relevant = SelfRAGVerifier.verify_relevance("gene", "unrelated text")
        self.assertFalse(is_relevant)

if __name__ == "__main__":
    unittest.main()
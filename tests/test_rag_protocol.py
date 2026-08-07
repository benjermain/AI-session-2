import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.vector_store import VectorStoreManager
from rag.ingest import ingest_policy_document
from rag.hybrid_rag import HybridRAG
from rag.agentic_rag import AgenticRAG
from rag.self_rag import SelfRAGVerifier

class TestRAGAndMCPProtocol(unittest.TestCase):
    def setUp(self):
        self.vector_store = VectorStoreManager(persist_directory="./test_chroma_db")
        docs = [
            "Vellora Biosafety Protocol 4.2b dictates cardiac risk screening for senior canine sedation.",
            "Standard fasting window prior to sedation is 8 hours for BSL-2 cleared procedures."
        ]
        if self.vector_store.client is not None:
            ingest_policy_document(docs[0], "cardiac", self.vector_store)
            ingest_policy_document(docs[1], "fasting", self.vector_store)
        self.hybrid_rag = HybridRAG(self.vector_store, docs)
        self.agentic_rag = AgenticRAG(self.hybrid_rag)

    def test_self_rag_verification_relevance(self):
        is_relevant = SelfRAGVerifier.verify_relevance("cardiac risk", "Protocol 4.2b dictates cardiac risk screening.")
        self.assertTrue(is_relevant)

        is_irrelevant = SelfRAGVerifier.verify_relevance("xyz_absent_term", "unrelated text")
        self.assertFalse(is_irrelevant)

    def test_hybrid_rag_search(self):
        results = self.hybrid_rag.hybrid_search("fasting window")
        self.assertIsInstance(results, list)

    def test_agentic_rag_retrieve(self):
        res = self.agentic_rag.retrieve_and_verify("cardiac risk")
        self.assertIn(res["status"], ["verified", "unverified"])

if __name__ == "__main__":
    unittest.main()
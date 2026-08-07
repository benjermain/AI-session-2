from typing import Dict, Any
from rag.hybrid_rag import HybridRAG
from rag.self_rag import SelfRAGVerifier

class AgenticRAG:
    """Multi-hop retrieval loop with query reformulation and verification."""
    def __init__(self, hybrid_rag: HybridRAG):
        self.hybrid_rag = hybrid_rag

    def retrieve_and_verify(self, query: str, max_iterations: int = 2) -> Dict[str, Any]:
        curr_query = query
        for step in range(max_iterations):
            docs = self.hybrid_rag.hybrid_search(curr_query, top_k=2)
            for doc in docs:
                if SelfRAGVerifier.verify_relevance(curr_query, doc):
                    return {"status": "verified", "context": doc, "hops": step + 1}
            curr_query = f"Vellora biosafety gene synthesis {query}"
        return {"status": "unverified", "context": "No verified context found", "hops": max_iterations}
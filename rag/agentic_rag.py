from typing import Dict, Any, Optional
from rag.self_rag import SelfRAGVerifier


class AgenticRAG:
    """Multi-hop retrieval loop with query reformulation and verification."""
    def __init__(self, hybrid_rag_or_vector_index, bm25_index=None):
        if bm25_index is not None:
            self.vector_index = hybrid_rag_or_vector_index
            self.bm25_index = bm25_index
            self.hybrid_rag = None
        else:
            self.hybrid_rag = hybrid_rag_or_vector_index
            self.vector_index = getattr(hybrid_rag_or_vector_index, 'vector_index', None)
            self.bm25_index = getattr(hybrid_rag_or_vector_index, 'bm25_index', None)

    def retrieve_and_verify(self, query: str, max_iterations: int = 2) -> Dict[str, Any]:
        curr_query = query
        for step in range(max_iterations):
            if self.hybrid_rag and hasattr(self.hybrid_rag, 'hybrid_search'):
                docs = self.hybrid_rag.hybrid_search(curr_query, top_k=2)
            else:
                docs = []
            for doc in docs:
                if SelfRAGVerifier.verify_relevance(curr_query, doc):
                    return {"status": "verified", "context": doc, "hops": step + 1}
            curr_query = f"Vellora biosafety gene synthesis {query}"
        return {"status": "unverified", "context": "No verified context found", "hops": max_iterations}

    def answer(self, question: str) -> Dict[str, Any]:
        step1 = {'retrieved': [], 'note': 'stub'}
        return {'answer': 'AGENTIC_STUB', 'steps': [step1]}

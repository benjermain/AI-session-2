from typing import List
from rag.vector_store import VectorStoreManager

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - exercised in minimal test environments
    BM25Okapi = None

class HybridRAG:
    """Hybrid search combining Vector similarity (ANN) + Keyword BM25."""
    def __init__(self, vector_store: VectorStoreManager, corpus_documents: List[str]):
        self.vector_store = vector_store
        self.corpus_documents = corpus_documents
        if BM25Okapi is None:
            self.bm25 = None
        else:
            tokenized_corpus = [doc.lower().split() for doc in corpus_documents]
            self.bm25 = BM25Okapi(tokenized_corpus) if corpus_documents else None

    def naive_search(self, query: str, top_k: int = 3) -> List[str]:
        results = self.vector_store.query(query_texts=[query], n_results=top_k)
        return results['documents'][0] if results and results.get('documents') else []

    def hybrid_search(self, query: str, top_k: int = 3) -> List[str]:
        vector_res = self.naive_search(query, top_k=top_k)
        if not self.bm25:
            return vector_res
        
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_k]
        bm25_res = [self.corpus_documents[i] for i in top_indices]
        
        combined = list(dict.fromkeys(vector_res + bm25_res))
        return combined[:top_k]
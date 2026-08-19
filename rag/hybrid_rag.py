from typing import List, Dict, Any, Union
from rag.embedder import embed_texts

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None


class HybridRAG:
    """Hybrid search combining Vector similarity (ANN) + Keyword BM25."""
    def __init__(self, vector_store, corpus_or_bm25):
        self.vector_store = vector_store
        self.vector_index = vector_store
        
        if isinstance(corpus_or_bm25, list):
            self.corpus_documents = corpus_or_bm25
            self.bm25_index = None
            if BM25Okapi is not None and corpus_or_bm25:
                tokenized_corpus = [doc.lower().split() for doc in corpus_or_bm25]
                self.bm25 = BM25Okapi(tokenized_corpus)
            else:
                self.bm25 = None
        else:
            self.bm25_index = corpus_or_bm25
            self.bm25 = None
            self.corpus_documents = []

    def naive_search(self, query: str, top_k: int = 3) -> List[str]:
        if hasattr(self.vector_store, 'query'):
            results = self.vector_store.query(query_texts=[query], n_results=top_k)
            return results['documents'][0] if results and results.get('documents') else []
        elif hasattr(self.vector_store, 'search'):
            q_emb = embed_texts([query])[0]
            results = self.vector_store.search(q_emb, top_k=top_k)
            return [r['text'] for r in results]
        return []

    def hybrid_search(self, query: str, top_k: int = 3) -> List[str]:
        vector_res = self.naive_search(query, top_k=top_k)
        if self.bm25:
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25.get_scores(tokenized_query)
            top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_k]
            bm25_res = [self.corpus_documents[i] for i in top_indices]
            combined = list(dict.fromkeys(vector_res + bm25_res))
            return combined[:top_k]
        elif self.bm25_index:
            bm25_ranks = self.bm25_index.search(query, top_k=top_k)
            bm25_texts = [d['text'] for d in bm25_ranks]
            combined = list(dict.fromkeys(vector_res + bm25_texts))
            return combined[:top_k]
        return vector_res

    def answer(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        q_emb = embed_texts([question])[0]
        if hasattr(self.vector_index, 'search'):
            vec_results = self.vector_index.search(q_emb, top_k=top_k)
        else:
            vec_texts = self.naive_search(question, top_k=top_k)
            vec_results = [{'text': t} for t in vec_texts]

        candidates = [r['text'] for r in vec_results]
        
        if self.bm25_index:
            bm25_ranks = self.bm25_index.search(question, top_k=top_k)
            fused = [doc for doc in bm25_ranks if doc['text'] in candidates]
            if not fused:
                fused = vec_results
        else:
            fused = vec_results

        return {'answer': 'HYBRID_STUB', 'retrieved': fused[:3]}

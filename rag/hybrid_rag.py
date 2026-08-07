"""
Hybrid RAG: vector retrieve followed by BM25 rerank.
"""
from typing import Dict
from rag.embedder import embed_texts

class HybridRAG:
    def __init__(self, vector_index, bm25_index):
        self.vector_index = vector_index
        self.bm25_index = bm25_index

    def answer(self, question: str, top_k: int = 5):
        q_emb = embed_texts([question])[0]
        vec_results = self.vector_index.search(q_emb, top_k=top_k)
        # use BM25 to rerank candidate texts
        candidates = [r['text'] for r in vec_results]
        bm25_ranks = self.bm25_index.search(question, top_k=top_k)
        # simple fusion: prefer bm25 results that are in the candidate set
        fused = []
        for doc in bm25_ranks:
            if doc['text'] in candidates:
                fused.append(doc)
        if not fused:
            fused = vec_results
        # stub LLM
        prompt = f"QUESTION: {question}\nCONTEXT:\n" + '\n\n'.join([d['text'] for d in fused[:3]])
        return {'answer': 'HYBRID_STUB', 'retrieved': fused[:3]}

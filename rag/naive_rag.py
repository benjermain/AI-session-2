"""
Naive RAG: vector retrieve top-k, concatenate and call LLM (LLM call is a stub here).
"""
from typing import List, Dict
from rag.embedder import embed_texts


def stub_llm_generate(prompt: str) -> str:
    return "LLM_RESPONSE: (stub)"+prompt[:200]

class NaiveRAG:
    def __init__(self, vector_index):
        self.vector_index = vector_index

    def answer(self, question: str, top_k: int = 3) -> Dict:
        q_emb = embed_texts([question])[0]
        retrieved = self.vector_index.search(q_emb, top_k=top_k)
        context = '\n\n'.join([r['text'] for r in retrieved])
        prompt = f"QUESTION: {question}\n\nCONTEXT:\n{context}\n\nAnswer:"
        answer = stub_llm_generate(prompt)
        return {'answer': answer, 'retrieved': retrieved}

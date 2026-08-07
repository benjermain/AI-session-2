"""
Simple BM25 adapter using rank_bm25 if installed; falls back to naive substring score.
"""
from typing import List, Dict

try:
    from rank_bm25 import BM25Okapi
except Exception:
    BM25Okapi = None

class BM25Index:
    def __init__(self):
        self.docs = []
        self.texts = []
        self.bm25 = None

    def add(self, id: str, text: str, metadata: Dict = None):
        self.docs.append({'id': id, 'text': text, 'metadata': metadata})
        self.texts.append(text.split())
        if BM25Okapi:
            self.bm25 = BM25Okapi(self.texts)

    def search(self, query: str, top_k: int = 5):
        if self.bm25:
            scores = self.bm25.get_scores(query.split())
            ranked = sorted(zip(self.docs, scores), key=lambda x: -x[1])
            return [d for d,s in ranked[:top_k]]
        # fallback: substring match
        ranked = sorted(self.docs, key=lambda d: query.lower() in d['text'].lower(), reverse=True)
        return ranked[:top_k]

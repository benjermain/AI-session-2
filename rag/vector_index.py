"""
Vector index adapter. This scaffold uses a simple in-memory vector store with metadata.
Replace with Chroma/Qdrant adapter.
"""
from typing import List, Dict, Any
import math

class InMemoryVectorIndex:
    def __init__(self):
        self.items: List[Dict[str, Any]] = []

    def add(self, id: str, embedding: List[float], text: str, metadata: Dict[str, Any] = None):
        self.items.append({'id': id, 'embedding': embedding, 'text': text, 'metadata': metadata})

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        # naive euclidean distance
        def dist(e):
            return math.sqrt(sum((a-b)**2 for a,b in zip(e['embedding'], query_embedding)))
        ranked = sorted(self.items, key=dist)
        return ranked[:top_k]

"""
Embedding adapter placeholder. Swap to OpenAI or sentence-transformers by editing this file.
"""
from typing import List


def embed_texts(texts: List[str]) -> List[List[float]]:
    # Return dummy embeddings (not suitable for production). Replace with OpenAI or SBERT call.
    return [[float(len(t))] for t in texts]

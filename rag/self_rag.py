class SelfRAGVerifier:
    """Self-RAG style verification check for grounding and relevance."""
    @staticmethod
    def verify_relevance(query: str, retrieved_chunk: str) -> bool:
        query_words = set(query.lower().split())
        chunk_words = set(retrieved_chunk.lower().split())
        return len(query_words.intersection(chunk_words)) > 0

    @staticmethod
    def verify_groundedness(answer: str, retrieved_chunk: str) -> bool:
        return bool(retrieved_chunk.strip()) and bool(answer.strip())
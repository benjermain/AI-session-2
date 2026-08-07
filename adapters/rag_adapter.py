"""
Adapter to call RAG pipelines from the agent loop.
Usage example:
  rag = HybridRAG(vector_index, bm25)
  if is_knowledge_query(question):
      return rag.answer(question)
"""
from rag.vector_index import InMemoryVectorIndex
from rag.bm25_index import BM25Index
from rag.hybrid_rag import HybridRAG

class RAGAdapter:
    def __init__(self):
        self.vector = InMemoryVectorIndex()
        self.bm25 = BM25Index()
        self.hybrid = HybridRAG(self.vector, self.bm25)

    def index_document(self, id: str, text: str, metadata: dict = None):
        # simplistic indexing: embed and add
        from rag.embedder import embed_texts
        emb = embed_texts([text])[0]
        self.vector.add(id=id, embedding=emb, text=text, metadata=metadata)
        self.bm25.add(id=id, text=text, metadata=metadata)

    def answer(self, question: str):
        return self.hybrid.answer(question)

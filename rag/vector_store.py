from typing import List, Dict, Any, Optional

try:
    import chromadb
except ImportError:  # pragma: no cover - exercised in minimal test environments
    chromadb = None


class VectorStoreManager:
    """Vector database setup using ChromaDB with HNSW ANN indexing and metadata filtering."""
    def __init__(self, persist_directory: str = "./chroma_db"):
        if chromadb is None:
            self.client = None
            self.collection = None
            return

        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="vellora_biosafety_policies",
            metadata={"hnsw:space": "cosine", "hnsw:construction_ef": 100}
        )

    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        if self.collection is None:
            return None
        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def query(self, query_texts: List[str], n_results: int = 3, filter_metadata: Optional[Dict[str, Any]] = None):
        """Pre/mid-search filtering via metadata payload."""
        if self.collection is None:
            return {"documents": [[]]}

        return self.collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=filter_metadata if filter_metadata else None
        )
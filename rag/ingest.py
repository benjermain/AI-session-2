import uuid
from typing import List
from rag.vector_store import VectorStoreManager

def chunk_text(text: str, chunk_size: int = 150, overlap: int = 30) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks

def ingest_policy_document(content: str, category: str, vector_store: VectorStoreManager):
    chunks = chunk_text(content)
    documents, metadatas, ids = [], [], []
    for idx, chunk in enumerate(chunks):
        documents.append(chunk)
        metadatas.append({"category": category, "chunk_id": idx})
        ids.append(f"{category}_{idx}_{str(uuid.uuid4())[:6]}")
    vector_store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
    return len(chunks)
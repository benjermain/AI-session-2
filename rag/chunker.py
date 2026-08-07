"""
Document chunker: split text into chunks with overlap.
"""
from typing import List, Dict
import math


def chunk_text(text: str, chunk_size_tokens: int = 500, overlap_tokens: int = 50) -> List[Dict]:
    # Very simple sentence-slicing approximation: split by sentences (periods).
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    chunks = []
    current = ''
    for s in sentences:
        if len((current + ' ' + s).split()) <= chunk_size_tokens:
            current = (current + ' ' + s).strip()
        else:
            if current:
                chunks.append({'text': current})
            current = s
    if current:
        chunks.append({'text': current})
    # naive overlap not implemented; real implementation should use token counts
    return chunks

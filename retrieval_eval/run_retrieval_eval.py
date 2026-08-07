"""
Run retrieval evaluation over the naive, hybrid, and agentic RAG implementations using the example questions.
This script is a simple harness: it loads questions.json and runs each architecture's answer() method.
"""
import json
from rag.naive_rag import NaiveRAG
from rag.hybrid_rag import HybridRAG
from rag.agentic_rag import AgenticRAG
from rag.vector_index import InMemoryVectorIndex
from rag.bm25_index import BM25Index
from rag.embedder import embed_texts


def run():
    with open('retrieval_eval/questions.json','r') as f:
        qs = json.load(f)
    # build a tiny corpus from the ground_truths for demonstration
    vector_index = InMemoryVectorIndex()
    bm25 = BM25Index()
    for i,q in enumerate(qs):
        text = q.get('ground_truth') + ' ' + q.get('citation','')
        emb = embed_texts([text])[0]
        vector_index.add(id=str(i), embedding=emb, text=text, metadata={'source_id': q['id']})
        bm25.add(id=str(i), text=text, metadata={'source_id': q['id']})

    naive = NaiveRAG(vector_index)
    hybrid = HybridRAG(vector_index, bm25)
    agentic = AgenticRAG(vector_index, bm25)

    results = []
    for q in qs:
        n = naive.answer(q['question'])
        h = hybrid.answer(q['question'])
        a = agentic.answer(q['question'])
        results.append({'id': q['id'], 'naive': n, 'hybrid': h, 'agentic': a})

    with open('retrieval_eval/results.json','w') as f:
        json.dump(results, f, indent=2)
    print('Wrote retrieval_eval/results.json')

if __name__ == '__main__':
    run()

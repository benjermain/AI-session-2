# AI-session-2: Memory + RAG scaffold

This branch adds a scaffolding for the memory, context evaluation, and retrieval (RAG) work described in the project assignment. It is intended as a complete starter implementation that you can run locally, extend, and use to produce the required evaluation tables and demo transcripts.

High-level contents added in this commit:
- memory/: short-term buffer, scratchpad, episodic store, semantic store, routing, consolidation
- context_eval/: four context-window strategies, long transcript generator, experiment runner
- rag/: chunker, embedder adapter, vector index adapter (Chroma placeholder), BM25 adapter, naive/hybrid/agentic RAG skeletons, Self-RAG checker
- retrieval_eval/: a small JSON of example questions and a runner
- adapters/: memory and rag adapters for integrating into an agent loop
- demo/: a 40-turn demo transcript
- run_all_experiments.sh: orchestrates context + retrieval experiments locally (example)

Defaults and notes
- This scaffold is intentionally dependency-light and uses in-memory stores so it can run without external services. Adapters are provided so you can switch to OpenAI embeddings, Chroma, or Qdrant by editing rag/embedder.py and rag/vector_index.py.
- No secrets or API keys are included. Please set environment variables for any production embedding or LLM provider.

See memory/README.md and rag/README.md for details on how to run the pieces.

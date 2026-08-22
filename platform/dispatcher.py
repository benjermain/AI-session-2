from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Dict, Generator, List, Optional

# Ensure workspace root is on sys.path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from mcp_server.db_client import get_payload_by_id, get_researcher_by_id
from mcp_server.registry import registry
from memory.consolidation import SemanticConsolidationEngine
from memory.episodic_store import EpisodicStore
from memory.router import PromoteOrDropRouter
from memory.semantic_store import SemanticStore
from memory.short_term import Scratchpad, ShortTermMemory
from planning.decomposition import DecompositionEngine
from planning.dynamic_decomposition import DynamicDecompositionEngine
from rag.agentic_rag import AgenticRAG
from rag.bm25_index import BM25Index
from rag.embedder import embed_texts
from rag.hybrid_rag import HybridRAG
from rag.vector_index import InMemoryVectorIndex
from state_graph.checkpointer import StateCheckpointer
from state_graph.workflows.bioreactor_batch import BioreactorBatchWorkflow
from state_graph.workflows.biosafety_escalation import BiosafetyEscalationWorkflow
from state_graph.workflows.vector_redesign import VectorRedesignWorkflow
from platform.llm_client import llm_client


class AgentDispatcher:
    """
    Central dispatch engine routing user and platform requests to the target agent
    (State Graphs 1-3, Memory/RAG Agent, and Decomposition Agent).
    """

    AGENTS_METADATA = [
        {
            "id": "bioreactor_batch",
            "name": "Bioreactor Batch Synthesis Agent",
            "type": "state_graph",
            "description": "Multi-stage automated vector synthesis, nutrient feeding, and sensor telemetry incubation with technician sign-off.",
            "techniques": ["Task Decomposition", "Hybrid RAG", "Durable Checkpointing", "HITL Sign-Off"],
            "icon": "flask-conical",
            "badge": "State Graph 1",
            "color": "cyan",
        },
        {
            "id": "biosafety_escalation",
            "name": "Dual-Use Biosafety Escalation Agent",
            "type": "state_graph",
            "description": "High-risk payload triage, IBC compliance policy verification, and human-in-the-loop review gating.",
            "techniques": ["Constrained ReAct", "Tree of Thoughts", "HITL Policy Gate", "Failure Tickets"],
            "icon": "shield-alert",
            "badge": "State Graph 2",
            "color": "amber",
        },
        {
            "id": "vector_redesign",
            "name": "Off-Target Vector Redesign Agent",
            "type": "state_graph",
            "description": "Iterative off-target anomaly detection and guided nucleotide sequence mutation search.",
            "techniques": ["LATS MCTS Search", "Constrained ReAct Assays", "Failure Ticket Recovery"],
            "icon": "dna",
            "badge": "State Graph 3",
            "color": "emerald",
        },
        {
            "id": "memory_rag",
            "name": "Grounded Biosafety RAG & Memory Agent",
            "type": "memory_rag",
            "description": "Conversational biosafety assistant backed by rolling short-term scratchpad, episodic/semantic stores, and hybrid retrieval.",
            "techniques": ["Hybrid Vector+BM25", "Agentic Multi-Hop", "Semantic Consolidation", "Rolling Scratchpad"],
            "icon": "brain",
            "badge": "Memory & RAG",
            "color": "purple",
        },
        {
            "id": "decomposition_planning",
            "name": "DAG Task Decomposition & Planning Agent",
            "type": "planning",
            "description": "Deconstructs complex clinical payload requirements into validated directed acyclic execution graphs with dynamic replanning.",
            "techniques": ["PlanDAG Generation", "Topological Execution", "Dynamic Replanning", "Grounded Environment"],
            "icon": "git-branch",
            "badge": "Decomposition",
            "color": "blue",
        },
    ]

    def __init__(self):
        # Workflows
        self.wf_bioreactor = BioreactorBatchWorkflow()
        self.wf_biosafety = BiosafetyEscalationWorkflow()
        self.wf_redesign = VectorRedesignWorkflow()

        # Planning engines
        self.decomposition_engine = DecompositionEngine()
        self.dynamic_decomposition_engine = DynamicDecompositionEngine(self.decomposition_engine)

        # Memory system
        self.scratchpad = Scratchpad(
            current_plan="Vellora Biosafety Platform Session",
            active_subgoal="Ready for multi-agent dispatch",
            safety_constraints=["Clearance must equal or exceed target Risk Tier"],
        )
        self.short_term_memory = ShortTermMemory(max_buffer_size=10, scratchpad=self.scratchpad)
        self.episodic_store = EpisodicStore()
        self.semantic_store = SemanticStore()
        self.router = PromoteOrDropRouter(episodic_store=self.episodic_store)
        self.consolidation_engine = SemanticConsolidationEngine(
            episodic_store=self.episodic_store,
            semantic_store=self.semantic_store,
        )

        # RAG system
        self.rag_corpus = [
            "Protocol 4.2b: All Risk Tier 3 viral vectors require BSL-3 laboratory containment and secondary IBC officer sign-off.",
            "Protocol 4.3: Fast-track synthesis permits automated processing only for Risk Tier 1 and Risk Tier 2 payloads with off-target score < 0.25.",
            "Protocol Bio-4.1: Bioreactor incubation requires continuous 37.0C temperature regulation with pH 7.20 to 7.40 and dissolved oxygen > 40%.",
            "Protocol Bio-4.3: Sterility threshold requires zero bacterial contamination and endotoxin level < 0.10 EU/mL before release.",
            "Policy Tier 4: Regulatory dual-use research concerns mandate automatic quarantine and Institutional Biosafety Committee sign-off.",
        ]
        self._init_rag_store()

    def _init_rag_store(self):
        self.vector_index = InMemoryVectorIndex()
        self.bm25_index = BM25Index()
        for idx, doc in enumerate(self.rag_corpus):
            emb = embed_texts([doc])[0]
            self.vector_index.add(str(idx), emb, doc, {"source": "policy_manual", "id": str(idx)})
            self.bm25_index.add(str(idx), doc, {"source": "policy_manual", "id": str(idx)})
        self.hybrid_rag = HybridRAG(self.vector_index, self.bm25_index)
        self.agentic_rag = AgenticRAG(self.hybrid_rag)

    def list_agents(self) -> List[Dict[str, Any]]:
        return self.AGENTS_METADATA

    def get_agent_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for agent in self.AGENTS_METADATA:
            if agent["id"] == agent_id:
                return agent
        return None

    def execute_agent(
        self,
        agent_id: str,
        message: str,
        payload_id: int = 1,
        researcher_id: int = 1,
        sequence: str = "ATCGATCGATCG",
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a prompt against the requested agent and returns structured execution data.
        """
        thread = thread_id or str(uuid.uuid4())
        agent_meta = self.get_agent_by_id(agent_id)
        if not agent_meta:
            raise ValueError(f"Unknown agent ID '{agent_id}'")

        # 1. Bioreactor Batch Synthesis Agent (Workflow 1)
        if agent_id == "bioreactor_batch":
            initial_state = {
                "request": message,
                "payload_id": payload_id,
                "researcher_id": researcher_id,
                "sequence": sequence,
                "thread_id": thread,
            }
            res = self.wf_bioreactor.run(initial_state, thread_id=thread)
            status = res.get("status", "COMPLETED")
            steps = [
                {"name": "Decompose Protocol", "status": "COMPLETED"},
                {"name": "Hybrid RAG Retrieval", "status": "COMPLETED"},
                {"name": "Bioreactor Loading", "status": "COMPLETED"},
                {"name": f"Incubation Telemetry ({res.get('sensor_cycle', 0)} cycles)", "status": "COMPLETED"},
            ]
            if status == "PAUSED":
                steps.append({"name": "Technician Sign-Off Gate", "status": "PAUSED"})
            elif status != "FAILED":
                steps.append({"name": "Technician Sign-Off Gate", "status": "COMPLETED"})
                steps.append({"name": "Harvest & Purification", "status": "COMPLETED"})

            summary = llm_client.generate_agent_response(
                agent_id="bioreactor_batch",
                user_message=message,
                execution_data=res,
                scratchpad=self.scratchpad.to_dict(),
            )

            return {
                "agent_id": agent_id,
                "thread_id": thread,
                "status": status,
                "summary": summary,
                "steps": steps,
                "data": res,
                "task_id": res.get("task_id"),
                "ticket_id": res.get("ticket_id"),
            }

        # 2. Dual-Use Biosafety Escalation Agent (Workflow 2)
        elif agent_id == "biosafety_escalation":
            state = {
                "request": message,
                "payload_id": payload_id,
                "researcher_id": researcher_id,
                "sequence": sequence,
                "thread_id": thread,
            }
            res = self.wf_biosafety.run(state)
            status = res.get("status", "COMPLETED")
            steps = [
                {"name": "Constrained ReAct Diagnostics", "status": "COMPLETED"},
                {"name": "Tree of Thoughts Risk Pathways", "status": "COMPLETED"},
            ]
            if status == "PAUSED":
                steps.append({"name": "IBC Policy Approval Gate", "status": "PAUSED"})
            elif status != "FAILED":
                steps.append({"name": "Safety Policy Cleared", "status": "COMPLETED"})

            summary = llm_client.generate_agent_response(
                agent_id="biosafety_escalation",
                user_message=message,
                execution_data=res,
                scratchpad=self.scratchpad.to_dict(),
            )

            return {
                "agent_id": agent_id,
                "thread_id": thread,
                "status": status,
                "summary": summary,
                "steps": steps,
                "data": res,
                "task_id": res.get("task_id"),
                "ticket_id": res.get("ticket_id"),
            }

        # 3. Off-Target Vector Redesign Agent (Workflow 3)
        elif agent_id == "vector_redesign":
            state = {
                "request": message,
                "payload_id": payload_id,
                "sequence": sequence,
                "safety_threshold": 0.35,
                "thread_id": thread,
            }
            res = self.wf_redesign.run(state)
            status = res.get("status", "COMPLETED")
            steps = [
                {"name": "Constrained ReAct Assay", "status": "COMPLETED"},
                {"name": f"LATS Mutation Search ({res.get('iteration', 1)} cycles)", "status": "COMPLETED"},
                {"name": "Grounded Safety Verification", "status": status},
            ]

            summary = llm_client.generate_agent_response(
                agent_id="vector_redesign",
                user_message=message,
                execution_data=res,
                scratchpad=self.scratchpad.to_dict(),
            )

            return {
                "agent_id": agent_id,
                "thread_id": thread,
                "status": status,
                "summary": summary,
                "steps": steps,
                "data": res,
                "ticket_id": res.get("ticket_id"),
            }

        # 4. Grounded Biosafety RAG & Memory Agent (Legacy Lab 2)
        elif agent_id == "memory_rag":
            # Record user turn in short-term buffer
            pruned = self.short_term_memory.add_message("user", message, {"payload_id": payload_id})
            if pruned:
                self.router.process_overflow(pruned, session_id=thread, researcher_id=researcher_id)

            # Retrieve from Hybrid RAG
            rag_docs = self.hybrid_rag.hybrid_search(message, top_k=2)
            rag_verified = self.agentic_rag.retrieve_and_verify(message)

            # Update scratchpad
            self.scratchpad.update_subgoal(f"Answering RAG query: {message[:40]}...")
            self.scratchpad.set_variable("last_retrieved_context", rag_docs[0] if rag_docs else "None")

            # Check MCP Tool capability (check if submit_synthesis_job is allowed)
            tool_calls = []
            try:
                reg_tool = registry.get("submit_synthesis_job", agent_id="memory_rag")
                tool_calls.append({"tool": "submit_synthesis_job", "status": "ENABLED", "desc": reg_tool.description})
            except Exception as e:
                tool_calls.append({"tool": "submit_synthesis_job", "status": "BLOCKED", "reason": str(e)})

            # Run periodic semantic consolidation pass
            cons_res = self.consolidation_engine.run_consolidation_pass()

            steps = [
                {"name": "Short-Term Memory Buffer Ingestion", "status": "COMPLETED"},
                {"name": "Hybrid Vector + BM25 Retrieval", "status": "COMPLETED"},
                {"name": "Self-RAG Groundedness Check", "status": "COMPLETED"},
            ]
            if cons_res.get("facts_updated", 0) > 0:
                steps.append({"name": f"Semantic Consolidation ({cons_res['facts_updated']} facts)", "status": "COMPLETED"})

            summary = llm_client.generate_agent_response(
                agent_id="memory_rag",
                user_message=message,
                execution_data={"rag_verified": rag_verified, "consolidation": cons_res},
                retrieved_context=rag_docs,
                scratchpad=self.scratchpad.to_dict(),
            )

            return {
                "agent_id": agent_id,
                "thread_id": thread,
                "status": "COMPLETED",
                "summary": summary,
                "steps": steps,
                "retrieved_context": rag_docs,
                "verification": rag_verified,
                "tool_calls": tool_calls,
                "consolidation": cons_res,
            }

        # 5. DAG Task Decomposition & Planning Agent (Legacy Lab 3)
        elif agent_id == "decomposition_planning":
            plan = self.decomposition_engine.decompose(message, payload_id=payload_id)
            dynamic_result = self.dynamic_decomposition_engine.run(
                message,
                executor=lambda t: {"task_id": t.id, "status": "ok", "off_target": False},
            )
            order = plan.execution_order()

            steps = [{"name": f"Subtask: {t.name}", "status": "COMPLETED"} for t in plan.subtasks]
            
            summary = llm_client.generate_agent_response(
                agent_id="decomposition_planning",
                user_message=message,
                execution_data={"plan": plan.model_dump(), "execution_order": order, "dynamic_result": dynamic_result},
                scratchpad=self.scratchpad.to_dict(),
            )

            return {
                "agent_id": agent_id,
                "thread_id": thread,
                "status": "COMPLETED",
                "summary": summary,
                "steps": steps,
                "plan": plan.model_dump(),
                "execution_order": order,
                "dynamic_result": dynamic_result,
            }

        return {"error": f"Unknown agent '{agent_id}'"}

    def add_rag_document(self, text: str, source: str = "custom_upload") -> Dict[str, Any]:
        """Dynamically adds a new document to the live RAG indexes."""
        doc_id = str(len(self.rag_corpus))
        self.rag_corpus.append(text)
        emb = embed_texts([text])[0]
        self.vector_index.add(doc_id, emb, text, {"source": source, "id": doc_id})
        self.bm25_index.add(doc_id, text, {"source": source, "id": doc_id})
        return {"status": "ADDED", "doc_id": doc_id, "total_docs": len(self.rag_corpus)}

    def delete_rag_document(self, doc_id: str) -> Dict[str, Any]:
        """Deletes a document from the RAG store and re-indexes."""
        try:
            idx = int(doc_id)
            if 0 <= idx < len(self.rag_corpus):
                removed = self.rag_corpus.pop(idx)
                # Re-index
                self._init_rag_store()
                return {"status": "DELETED", "removed": removed, "remaining_docs": len(self.rag_corpus)}
        except Exception as e:
            return {"error": str(e)}
        return {"error": f"Document ID '{doc_id}' not found"}

    def get_memory_dashboard_state(self) -> Dict[str, Any]:
        """Returns the current state of Scratchpad, Buffer, Facts, and Decisions."""
        ctx = self.short_term_memory.get_working_context()
        facts = [f.to_dict() for f in self.semantic_store.list_all_active_facts()]
        history = self.router.get_decision_history(limit=10)
        return {
            "scratchpad": ctx["scratchpad"],
            "buffer_count": ctx["buffer_count"],
            "max_buffer_size": ctx["max_buffer_size"],
            "transcript": ctx["active_transcript"],
            "active_facts": facts,
            "router_history": history,
        }


# Singleton dispatcher instance
dispatcher = AgentDispatcher()

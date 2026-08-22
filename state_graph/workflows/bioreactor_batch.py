from __future__ import annotations

import uuid
from typing import Any, Mapping, Optional

from mcp_server.db_client import get_payload_by_id
from planning.decomposition import DecompositionEngine
from rag.bm25_index import BM25Index
from rag.embedder import embed_texts
from rag.hybrid_rag import HybridRAG
from rag.vector_index import InMemoryVectorIndex
from state_graph.checkpointer import StateCheckpointer
from state_graph.hitl import HITLNode, HITLPause
from state_graph.ticket_system import FailureTicketEngine


DEFAULT_BIOREACTOR_PROTOCOLS = [
    "Protocol Bio-4.1: Standard viral vector incubation requires 37.0C +/- 0.5C with pH 7.20 to 7.40 and dissolved oxygen > 40%.",
    "Protocol Bio-4.2: High-density batch synthesis requires multi-stage nutrient feed at hour 4 and sterility sampling prior to harvest.",
    "Protocol Bio-4.3: Sterility threshold requires zero bacterial contamination and endotoxin level < 0.10 EU/mL before release.",
]


class BioreactorBatchWorkflow:
    """
    Stateful workflow managing multi-stage bioreactor batch synthesis and incubation.
    
    Two LLM Additions:
      1. Task Decomposition: Breaks batch manufacturing recipe into phased PlanDAG subtasks.
      2. Grounded RAG: Retrieves vector-specific incubation profiles and sterility tolerances.
    
    Includes durable SQLite checkpointing after every node transition and HITL technician gates.
    """

    ALLOWED_STAGES = frozenset({"preparation", "loading", "incubation", "sterility_check", "harvest"})

    def __init__(
        self,
        decomposition_engine: Optional[DecompositionEngine] = None,
        hybrid_rag: Optional[HybridRAG] = None,
        requested_by: Optional[str] = None,
        max_sensor_cycles: int = 3,
    ):
        self.decomposition = decomposition_engine or DecompositionEngine()
        self.rag = hybrid_rag or self._build_default_rag()
        self.hitl = HITLNode("bioreactor_batch", requested_by)
        self.failures = FailureTicketEngine("bioreactor_batch")
        self.checkpointer = StateCheckpointer("bioreactor_batch")
        self.max_sensor_cycles = max_sensor_cycles

    @staticmethod
    def _build_default_rag() -> HybridRAG:
        v_idx = InMemoryVectorIndex()
        bm25 = BM25Index()
        for idx, text in enumerate(DEFAULT_BIOREACTOR_PROTOCOLS):
            emb = embed_texts([text])[0]
            v_idx.add(str(idx), emb, text, {"source": "bioreactor_manual"})
            bm25.add(str(idx), text, {"source": "bioreactor_manual"})
        return HybridRAG(v_idx, bm25)

    def decompose_protocol(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """LLM Addition 1: Task Decomposition of the batch recipe into phased protocol stages."""
        request = str(state.get("request", "Execute bioreactor batch synthesis and incubation for payload."))
        payload_id = int(state.get("payload_id", 1))
        dag = self.decomposition.decompose(request, payload_id=payload_id)
        
        stages = [t.name for t in dag.subtasks]
        return {
            **dict(state),
            "stages": stages,
            "execution_order": dag.execution_order(),
            "decomposition_plan": dag.model_dump(),
            "current_stage": "preparation",
        }

    def retrieve_incubation_protocol(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """LLM Addition 2: Hybrid RAG retrieval of incubation curves and sterility tolerances."""
        query = f"bioreactor incubation temperature pH sterility tolerances for payload {state.get('payload_id', 1)}"
        retrieved_docs = self.rag.hybrid_search(query, top_k=2)
        
        return {
            **dict(state),
            "retrieved_protocols": retrieved_docs,
            "target_temp_c": 37.0,
            "target_ph_range": [7.20, 7.40],
            "sterility_threshold_eumL": 0.10,
            "current_stage": "loading",
        }

    def load_bioreactor(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Prepares and loads vessel with payload and buffer media."""
        payload_id = int(state.get("payload_id", 1))
        payload = get_payload_by_id(payload_id)
        if payload is None:
            raise ValueError(f"Payload ID {payload_id} not found in database")
        
        vessel_id = state.get("vessel_id", f"BIO-VESSEL-{payload_id:03d}")
        return {
            **dict(state),
            "vessel_id": vessel_id,
            "payload_name": payload["name"],
            "risk_tier": payload["risk_tier"],
            "vessel_status": "LOADED_AND_SEALED",
            "current_stage": "incubation",
            "sensor_cycle": 0,
        }

    def incubation_sensor_cycle(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Simulates iterative telemetry polling for temperature, pH, and cell viability."""
        cycle = int(state.get("sensor_cycle", 0)) + 1
        # Simulated sensor telemetry
        current_temp = round(36.8 + (cycle * 0.1), 2)
        current_ph = round(7.28 + (cycle * 0.02), 2)
        viability_pct = round(92.0 + (cycle * 2.0), 1)
        
        telemetry = state.get("telemetry_history", [])
        telemetry.append({
            "cycle": cycle,
            "temp_c": current_temp,
            "ph": current_ph,
            "viability_pct": viability_pct,
            "status": "NOMINAL",
        })
        
        incubation_complete = cycle >= self.max_sensor_cycles
        return {
            **dict(state),
            "sensor_cycle": cycle,
            "current_temp": current_temp,
            "current_ph": current_ph,
            "viability_pct": viability_pct,
            "telemetry_history": telemetry,
            "incubation_complete": incubation_complete,
            "current_stage": "sterility_check" if incubation_complete else "incubation",
        }

    def harvest_and_purify(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Final harvesting, filtration, and yield calculation."""
        yield_mg_l = round(450.0 + (state.get("sensor_cycle", 1) * 35.0), 2)
        return {
            **dict(state),
            "harvest_yield_mg_l": yield_mg_l,
            "purity_pct": 98.4,
            "status": "COMPLETED",
            "current_stage": "harvest",
        }

    def run(self, state: Mapping[str, Any], thread_id: Optional[str] = None) -> dict[str, Any]:
        """Executes the stateful bioreactor workflow with persistent checkpointing."""
        thread = thread_id or state.get("thread_id") or str(uuid.uuid4())
        current = {**dict(state), "thread_id": thread}

        # Step 1: Task Decomposition
        if "decomposition_plan" not in current:
            result = self.failures.run("decompose_protocol", current, self.decompose_protocol)
            if result.get("status") == "FAILED":
                return result
            current = result
            self.checkpointer.save(thread, "decompose_protocol", current)

        # Step 2: RAG Protocol Retrieval
        if "retrieved_protocols" not in current:
            result = self.failures.run("retrieve_incubation_protocol", current, self.retrieve_incubation_protocol)
            if result.get("status") == "FAILED":
                return result
            current = result
            self.checkpointer.save(thread, "retrieve_incubation_protocol", current)

        # Step 3: Bioreactor Loading
        if current.get("vessel_status") != "LOADED_AND_SEALED":
            result = self.failures.run("load_bioreactor", current, self.load_bioreactor)
            if result.get("status") == "FAILED":
                return result
            current = result
            self.checkpointer.save(thread, "load_bioreactor", current)

        # Step 4: Incubation Sensor Loop (Cycles)
        while not current.get("incubation_complete", False):
            result = self.failures.run("incubation_sensor_cycle", current, self.incubation_sensor_cycle)
            if result.get("status") == "FAILED":
                return result
            current = result
            self.checkpointer.save(thread, f"incubation_cycle_{current['sensor_cycle']}", current)

        # Step 5: HITL Sterility & Technician Sign-Off Gate
        if current.get("technician_sign_off") is None:
            current["hitl_reason"] = "Technician manual sterility check and sign-off required prior to vessel harvest."
            self.checkpointer.save(thread, "awaiting_technician_sign_off", current)
            try:
                return self.hitl(current)
            except HITLPause as pause:
                return {
                    "status": "PAUSED",
                    "task_id": pause.task_id,
                    "workflow": pause.workflow,
                    "thread_id": thread,
                    "state": pause.state,
                }

        # Step 6: Harvest and Purify
        if current.get("status") != "COMPLETED":
            result = self.failures.run("harvest_and_purify", current, self.harvest_and_purify)
            if result.get("status") == "FAILED":
                return result
            current = result
            self.checkpointer.save(thread, "harvest_and_purify", current)

        return current

    def resume(self, task_id: str, approved: bool, state: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        """Resumes workflow from HITL technician sign-off gate."""
        hitl_res = self.hitl.resume(task_id, approved, state)
        resumed_state = dict(hitl_res["state"])
        resumed_state["technician_sign_off"] = "APPROVED" if approved else "REJECTED"
        thread_id = resumed_state.get("thread_id", str(uuid.uuid4()))

        if not approved:
            resumed_state["status"] = "REJECTED"
            self.checkpointer.save(thread_id, "technician_rejected", resumed_state)
            return resumed_state

        # Continue to harvest
        return self.run(resumed_state, thread_id=thread_id)

    def resume_from_checkpoint(self, thread_id: str) -> dict[str, Any]:
        """Resumes workflow directly from the latest persisted SQLite checkpoint."""
        latest = self.checkpointer.get_latest(thread_id)
        if latest is None:
            raise KeyError(f"No checkpoint found for thread_id '{thread_id}'")
        return self.run(latest.state, thread_id=thread_id)

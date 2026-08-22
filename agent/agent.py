import argparse
import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
except ImportError:  # pragma: no cover - exercised in minimal test environments
    ClientSession = object
    StdioServerParameters = object
    stdio_client = None
    sse_client = None

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memory.short_term import ShortTermMemory, Scratchpad
from memory.buffer import RollingBuffer
from memory.episodic_store import EpisodicStore
from memory.semantic_store import SemanticStore
from memory.router import PromoteOrDropRouter
from memory.consolidation import SemanticConsolidationEngine
from context_eval.strategies import apply_context_strategy
from rag.vector_store import VectorStoreManager
from rag.ingest import ingest_policy_document
from rag.hybrid_rag import HybridRAG
from rag.agentic_rag import AgenticRAG
from planning.llm_adapter import LLMAdapter
from mcp_server.server import process_mcp_protocol_request


DEFAULT_BIOSAFETY_POLICIES = [
    "Vellora Biosafety Protocol 4.2b: All gene synthesis requests for Risk Tier 3 and Tier 4 payloads require BSL-3 or BSL-4 verified clearance. Cardiac risk screening is mandatory for senior canine sedation protocols.",
    "Vellora Fast-Track Vector Protocol 1.8: BSL-1 clearance permits synthesis only for Tier 1 non-pathogenic GFP markers and standard reporter constructs.",
    "Vellora Off-Target Safety Standard 3.1: Any sequence with aggregate off-target alignment score exceeding 0.40 must be rejected or flagged for secondary review.",
    "Standard fasting window prior to sedation is 8 hours for BSL-2 cleared procedures.",
    "Dual-use research of concern (DURC) policy: Viral vector modifications with potential transmission enhancement require institutional biosafety committee (IBC) sign-off."
]


class Agent:
    """
    Vellora Bio Unified Agent:
    Seamlessly integrates:
    1. Long-Term Memory Architecture (Short-Term Buffer, Scratchpad, Episodic/Semantic Stores, Router, Consolidation)
    2. Grounded RAG Knowledge Engine (Vector Store, BM25 Hybrid Search, Agentic Multi-Hop RAG)
    3. Dynamic Context Window Management (Observation Masking, Sliding Window, Recursive Summarization, Zone Pruning)
    4. Reasoning Engine & LLM Adapter (4-zone prompt structure passed to model)
    5. MCP Client & Tool Orchestration (Defensive Synthesis, Off-Target Simulation)
    """
    def __init__(
        self,
        session: Optional[ClientSession] = None,
        max_buffer_size: int = 4,
        vector_db_path: str = "./chroma_db",
        active_context_strategy: str = "observation_masking",
        base_llm: Any = None
    ):
        self.session = session
        self.active_context_strategy = active_context_strategy

        # 1. Initialize Reasoning Engine (LLM Adapter)
        self.llm = LLMAdapter(base_llm=base_llm, mock_mode=True)

        # 2. Initialize RAG Subsystem
        self.vector_store = VectorStoreManager(persist_directory=vector_db_path)
        self.policy_corpus = list(DEFAULT_BIOSAFETY_POLICIES)

        # Populate vector store if client is active
        if self.vector_store.client is not None:
            try:
                for idx, doc in enumerate(self.policy_corpus):
                    ingest_policy_document(doc, f"policy_doc_{idx}", self.vector_store)
            except Exception:
                pass

        self.hybrid_rag = HybridRAG(self.vector_store, self.policy_corpus)
        self.agentic_rag = AgenticRAG(self.hybrid_rag)

        # 3. Initialize Memory Subsystem
        self.scratchpad = Scratchpad(
            current_plan="Interactive Gene Synthesis & Biosafety Tracking Session",
            active_subgoal="Initializing agent subsystems",
            working_variables={},
            safety_constraints=["BSL clearance must satisfy target Risk Tier"]
        )
        self.short_term = ShortTermMemory(max_buffer_size=max_buffer_size, scratchpad=self.scratchpad)

        # 4. RollingBuffer: secondary managed window used by get_managed_context_window()
        #    and prune_to_tokens(). Shares the same default_strategy as the agent so
        #    every call to record_turn() is mirrored here automatically.
        self.rolling_buffer = RollingBuffer(
            max_turns=max_buffer_size * 4,
            default_strategy=active_context_strategy
        )

        self.episodic_store = EpisodicStore()
        self.semantic_store = SemanticStore()
        self.router = PromoteOrDropRouter(episodic_store=self.episodic_store)
        self.consolidation = SemanticConsolidationEngine(
            episodic_store=self.episodic_store,
            semantic_store=self.semantic_store
        )

    def execute_rag_pipeline(self, user_query: str) -> Dict[str, Any]:
        """Executes server protocol request and verified agentic RAG pipeline."""
        mcp_req = json.dumps({"method": "mcp/rag/query", "params": {"query": user_query}, "id": 101})
        protocol_res = process_mcp_protocol_request(mcp_req)
        rag_res = self.agentic_rag.retrieve_and_verify(user_query)
        return {"protocol_response": json.loads(protocol_res), "rag_result": rag_res}

    def retrieve_policy_grounding(self, query: str, update_scratchpad: bool = True) -> Dict[str, Any]:
        """
        Queries RAG knowledge base for biosafety policies and grounds the agent's active scratchpad.
        """
        hybrid_results = self.hybrid_rag.hybrid_search(query, top_k=2)
        agentic_result = self.agentic_rag.retrieve_and_verify(query)

        grounding_text = hybrid_results[0] if hybrid_results else agentic_result.get("context", "")
        
        if update_scratchpad and grounding_text:
            constraint = f"[RAG Policy Grounded]: {grounding_text[:120]}"
            self.scratchpad.add_safety_constraint(constraint)

        return {
            "query": query,
            "hybrid_matches": hybrid_results,
            "agentic_result": agentic_result,
            "grounding_text": grounding_text,
        }

    def record_turn(
        self,
        role: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: str = "default_session",
        researcher_id: Optional[int] = None
    ) -> List[Any]:
        """
        Records dialogue/tool turn in BOTH ShortTermMemory and RollingBuffer.
        ShortTermMemory triggers Promote-or-Drop routing when its fixed window overflows.
        RollingBuffer maintains a longer sliding history with dynamic context strategy applied
        on every get_managed_context() call, giving the agent a dual-level memory architecture.
        """
        # Primary: ShortTermMemory (fixed window + router)
        pruned_items = self.short_term.add_message(role, content, metadata=metadata)
        decisions = []
        if pruned_items:
            decisions = self.router.process_overflow(
                pruned_items,
                session_id=session_id,
                researcher_id=researcher_id or 1
            )

        # Secondary: RollingBuffer (longer window, strategy-managed)
        self.rolling_buffer.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
        })

        return decisions

    def build_managed_context_for_llm(self, strategy: Optional[str] = None) -> List[tuple[str, str]]:
        """
        Constructs the 4-zone prompt seen by the LLM.

        Delegates entirely to ShortTermMemory.build_llm_messages(), which internally calls
        apply_context_strategy() from context_eval.strategies — guaranteeing the chosen
        strategy (sliding_window, observation_masking, recursive_summarization, or
        zone_based_pruning) is applied to every prompt sent to the model.

        Zone 1: System Persona & Compliance Instructions
        Zone 2: Active Working Scratchpad & RAG Grounded Safety Constraints
        Zone 3: Context-Managed Dialogue Transcript (processed by apply_context_strategy)
        Zone 4: Current Active User Request
        """
        strat = strategy or self.active_context_strategy
        system_intro = "You are Vellora Bio Agent, an AI biosafety assistant for laboratory genetic synthesis."
        return self.short_term.build_llm_messages(
            system_prompt=system_intro,
            strategy_name=strat
        )

    def get_managed_context_window(self, strategy: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns the active context summary produced by ShortTermMemory (short fixed window)
        merged with what RollingBuffer tracks over the longer history.
        Both run apply_context_strategy internally, demonstrating dual-level context management.
        """
        strat = strategy or self.active_context_strategy
        # ShortTermMemory view (fixed window, router-managed)
        short_ctx = self.short_term.get_managed_context(strategy_name=strat)
        # RollingBuffer view (longer history, token-budget-managed)
        rolling_managed = self.rolling_buffer.get_managed_context(strategy=strat)
        short_ctx["rolling_buffer_managed_count"] = len(rolling_managed)
        short_ctx["rolling_buffer_strategy"] = strat
        return short_ctx

    async def execute_synthesis_workflow(
        self,
        researcher_id: int,
        payload_id: int,
        sequence: str,
        session_id: str = "interactive_sess_01"
    ) -> Dict[str, Any]:
        """
        End-to-end grounded synthesis workflow:
        1. RAG Policy Grounding -> Updates Scratchpad
        2. Record User Turn in Memory
        3. Context Window Assembly via apply_context_strategy
        4. Agent Reasoning / LLM Decision over Managed Context
        5. Defensive MCP Tool Execution
        6. Tool Response Memory Recording & Observation Masking
        7. Semantic Memory Consolidation
        """
        self.scratchpad.update_subgoal(f"Validating synthesis job for researcher {researcher_id} on payload {payload_id}")
        self.scratchpad.set_variable("researcher_id", researcher_id)
        self.scratchpad.set_variable("payload_id", payload_id)
        self.scratchpad.set_variable("sequence", sequence)

        # 1. RAG Grounding: Fetch relevant biosafety policies
        rag_grounding = self.retrieve_policy_grounding(f"BSL clearance authorization Risk Tier {payload_id}")

        # 2. Record User Turn in Memory
        user_msg = f"Submit synthesis job for researcher={researcher_id}, payload={payload_id}, seq={sequence}"
        user_overflow = self.record_turn("user", user_msg, session_id=session_id, researcher_id=researcher_id)

        # 3. Context Window Management: Construct managed LLM messages using apply_context_strategy
        llm_messages = self.build_managed_context_for_llm(strategy=self.active_context_strategy)

        # 4. Agent Reasoning: Invoke LLM over the context-managed prompt
        agent_thought = self.llm.invoke(llm_messages)
        self.record_turn("assistant", f"[Agent Decision]: {agent_thought.content[:100]}", session_id=session_id)

        # 5. Execute Defensive MCP Tool
        resp_text = ""
        if self.session is not None and hasattr(self.session, "call_tool"):
            result = await self.session.call_tool("submit_synthesis_job", {
                "researcher_id": researcher_id,
                "payload_id": payload_id,
                "sequence": sequence
            })
            resp_text = result.content[0].text if result.content else str(result)
        else:
            # Fallback for direct testing without active transport
            from mcp_server.tools.defensive_synthesis import handle_submit_synthesis_job
            resp_text = json.dumps(handle_submit_synthesis_job(researcher_id, payload_id, sequence), indent=2)

        # 6. Record Tool Turn in Memory
        tool_overflow = self.record_turn(
            "tool",
            resp_text,
            metadata={"tool_name": "submit_synthesis_job", "researcher_id": researcher_id, "payload_id": payload_id},
            session_id=session_id,
            researcher_id=researcher_id
        )

        # 7. Run Semantic Memory Consolidation Pass
        cons_res = self.consolidation.run_consolidation_pass()

        # 8. Obtain active managed context summary
        managed_ctx = self.get_managed_context_window()

        return {
            "rag_grounding": rag_grounding,
            "agent_thought": agent_thought.content,
            "llm_prompt_messages_count": len(llm_messages),
            "server_response": resp_text,
            "user_overflow_decisions": user_overflow,
            "tool_overflow_decisions": tool_overflow,
            "consolidation_result": cons_res,
            "managed_context": managed_ctx,
        }

    async def execute_simulation_workflow(
        self,
        payload_id: int,
        sequence: str,
        session_id: str = "interactive_sess_01"
    ) -> Dict[str, Any]:
        """
        End-to-end grounded simulation workflow:
        1. RAG Off-Target Policy Grounding
        2. MCP Simulation Tool Execution (produces bulky 3KB+ JSON)
        3. Automatic Context Window Management (apply_context_strategy observation masking)
        4. Memory Recording & Overflow Routing
        """
        self.scratchpad.update_subgoal(f"Executing genome-wide off-target alignment simulation for payload {payload_id}")
        self.scratchpad.set_variable("payload_id", payload_id)
        self.scratchpad.set_variable("sequence", sequence)

        # 1. RAG Grounding
        rag_grounding = self.retrieve_policy_grounding("Off-target safety threshold alignment score")

        # 2. Record User Turn
        user_msg = f"Run simulation for payload={payload_id}, seq={sequence}"
        user_overflow = self.record_turn("user", user_msg, session_id=session_id)

        # 3. Context Management: Build prompt context before calling simulation
        llm_messages = self.build_managed_context_for_llm(strategy="observation_masking")

        # 4. Execute MCP Simulation Tool
        resp_text = ""
        if self.session is not None and hasattr(self.session, "call_tool"):
            result = await self.session.call_tool("simulate_off_target_effects", {
                "payload_id": payload_id,
                "sequence": sequence
            })
            resp_text = result.content[0].text if result.content else str(result)
        else:
            from mcp_server.tools.progress_off_target import handle_simulate_off_target_effects
            resp_text = json.dumps(handle_simulate_off_target_effects(payload_id, sequence), indent=2)

        # 5. Record Tool Turn (Bulky Tool JSON)
        tool_overflow = self.record_turn(
            "tool",
            resp_text,
            metadata={"tool_name": "simulate_off_target_effects", "is_tool_output": True},
            session_id=session_id
        )

        # 6. Apply Active Context Management (Observation Masking suppresses raw JSON in downstream prompt)
        managed_ctx = self.get_managed_context_window("observation_masking")
        post_tool_llm_messages = self.build_managed_context_for_llm(strategy="observation_masking")

        return {
            "rag_grounding": rag_grounding,
            "server_response": resp_text,
            "user_overflow_decisions": user_overflow,
            "tool_overflow_decisions": tool_overflow,
            "managed_context": managed_ctx,
            "post_tool_llm_messages": post_tool_llm_messages,
        }

    def chat_turn(self, user_query: str, strategy: Optional[str] = None, session_id: str = "interactive") -> Dict[str, Any]:
        """
        Processes a generic user query through the full context-managed and RAG-grounded pipeline:
        1. RAG policy lookup if safety terms are present.
        2. Adds user turn to memory.
        3. Builds context-managed prompt via apply_context_strategy.
        4. Invokes LLM over managed context.
        5. Records assistant turn.
        """
        rag_info = self.retrieve_policy_grounding(user_query)
        self.record_turn("user", user_query, session_id=session_id)
        
        # Build prompt using active context management strategy
        llm_messages = self.build_managed_context_for_llm(strategy=strategy)
        response = self.llm.invoke(llm_messages)
        self.record_turn("assistant", response.content, session_id=session_id)

        return {
            "response": response.content,
            "rag_grounding": rag_info,
            "managed_messages_count": len(llm_messages),
            "strategy_used": strategy or self.active_context_strategy
        }


VelloraAgent = Agent


async def run_agent(transport: str = "stdio", sse_url: str = "http://127.0.0.1:8000/sse", interactive: bool = True):
    print("=" * 65)
    print(f" VELLORA BIO - INTEGRATED MCP AGENT (Transport: {transport.upper()})")
    print(" Powered by RAG Grounding, Context Window Management & Long-Term Memory")
    print("=" * 65)

    if transport == "sse":
        print(f"\n[1] Connecting to Remote MCP Server via SSE Transport ({sse_url})...")
        async with sse_client(sse_url) as (read, write):
            async with ClientSession(read, write) as session:
                await execute_agent_session(session, interactive)
    else:
        print("\n[1] Connecting to Local MCP Server via stdio Transport...")
        server_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp_server", "server.py"))
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script, "--transport", "stdio"],
            env=os.environ.copy()
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await execute_agent_session(session, interactive)


async def execute_agent_session(session: ClientSession, interactive: bool):
    print("\n[2] Initiating Capability Negotiation (Handshake)...")
    initialize_result = await session.initialize()
    print("  Server Handshake Successful!")
    print(f"    Server Name:    {initialize_result.serverInfo.name}")
    print(f"    Server Version: {initialize_result.serverInfo.version}")

    print("\n[3] Discovering Available Tools from Server...")
    tools_response = await session.list_tools()
    print(f"  Discovered {len(tools_response.tools)} Registered Tools:")
    for tool in tools_response.tools:
        print(f"     * Tool: {tool.name} -> {tool.description[:70]}...")

    # Initialize Integrated Agent with RAG, Memory, Context Management, LLM, and MCP session
    agent = VelloraAgent(session=session, max_buffer_size=4)
    print("\n[4] Initialized Integrated Agent Subsystems:")
    print("    - Grounded RAG (Hybrid BM25 + Vector Search + Agentic Multi-Hop)")
    print("    - Long-Term Memory (Scratchpad, Rolling Buffer, Episodic/Semantic Stores, Router)")
    print("    - Dynamic Context Window Management (Observation Masking & Zone Pruning)")
    print("    - LLM Adapter & 4-Zone Prompt Assembler")

    if not interactive:
        await run_automated_demo(agent)
        return

    await run_interactive_mode(agent)


async def run_interactive_mode(agent: VelloraAgent):
    print("\n" + "=" * 65)
    print(" VELLORA BIO - INTERACTIVE AGENT TERMINAL")
    print("=" * 65)

    loop = asyncio.get_event_loop()

    while True:
        print("\nSelect an action:")
        print("  1: Submit Synthesis Job (RAG Grounding -> Context Masking -> LLM Reasoning -> MCP Tool)")
        print("  2: Run Off-Target Simulation (RAG Check -> Large JSON -> Observation Masking)")
        print("  3: Query Biosafety Policy Knowledge Base (Hybrid & Agentic RAG)")
        print("  4: View Active Memory & Managed Context Window Dashboard")
        print("  5: Test Context Window Management Strategy (Sliding, Masking, Summary, Zone)")
        print("  6: Free-Form Agent Chat (Processes via Context Management & RAG)")
        print("  7: Trigger Periodic Semantic Memory Consolidation Pass")
        print("  8: Exit")

        choice = await loop.run_in_executor(None, input, "\nEnter choice (1-8): ")
        choice = choice.strip()

        if choice == "8" or choice.lower() in ["exit", "quit"]:
            print("\nExiting Interactive Terminal. Goodbye!")
            break

        if choice == "1":
            print("\n--- RESEARCHER IDENTITIES ---")
            print("  1: Dr. Alice Vance (BSL-1 Clearance - Molecular Biology)")
            print("  2: Dr. Bob Smith (BSL-2 Clearance - Genomics)")
            print("  3: Dr. Clara Oswald (BSL-3 Clearance - Virology & Vectors)")
            print("  4: Dr. David Banner (BSL-4 Clearance - High Containment Lab)")

            res_input = await loop.run_in_executor(None, input, "Enter Researcher ID (1-4) [default: 1]: ")
            res_id = int(res_input.strip()) if res_input.strip().isdigit() else 1

            print("\n--- GENETIC PAYLOADS ---")
            print("  1: GFP Marker Construct (Risk Tier 1 - Safe)")
            print("  2: CRISPR Cas9 Target Region (Risk Tier 2)")
            print("  3: Attenuated Viral Vector Component (Risk Tier 3)")
            print("  4: High Risk Regulatory Construct (Risk Tier 4 - Dangerous)")

            pay_input = await loop.run_in_executor(None, input, "Enter Payload ID (1-4) [default: 4]: ")
            pay_id = int(pay_input.strip()) if pay_input.strip().isdigit() else 4

            seq_input = await loop.run_in_executor(None, input, "Enter DNA Sequence (ATCG characters) [default: ATCGATCG]: ")
            sequence = seq_input.strip().upper() if seq_input.strip() else "ATCGATCG"

            print(f"\n[PIPELINE START] Submitting Job -> Researcher ID: {res_id} | Payload ID: {pay_id} | Sequence: '{sequence}'")
            workflow_res = await agent.execute_synthesis_workflow(res_id, pay_id, sequence)

            print(f"\n[1. RAG POLICY GROUNDING]")
            print(f"  Grounded Policy: {workflow_res['rag_grounding']['grounding_text']}")

            print(f"\n[2. CONTEXT MANAGEMENT & AGENT REASONING]")
            print(f"  Managed LLM Prompt Messages Count: {workflow_res['llm_prompt_messages_count']}")
            print(f"  Agent Reasoning Output: {workflow_res['agent_thought']}")

            print("\n[3. SERVER RESPONSE]")
            print(workflow_res["server_response"])

            if workflow_res["user_overflow_decisions"] or workflow_res["tool_overflow_decisions"]:
                print(f"\n[4. MEMORY OVERFLOW ROUTING]")
                for d in workflow_res["user_overflow_decisions"] + workflow_res["tool_overflow_decisions"]:
                    print(f"  -> Router Decision: [{d.decision}] Reason: {d.reasoning}")

            if workflow_res["consolidation_result"].get("facts_updated", 0) > 0:
                print(f"\n[5. CONSOLIDATION PASS] Updated {workflow_res['consolidation_result']['facts_updated']} facts.")

        elif choice == "2":
            print("\n--- RUN SAFETY SIMULATION ---")
            pay_input = await loop.run_in_executor(None, input, "Enter Payload ID (1-4) [default: 1]: ")
            pay_id = int(pay_input.strip()) if pay_input.strip().isdigit() else 1

            seq_input = await loop.run_in_executor(None, input, "Enter DNA Sequence [default: ATCGATCGATCG]: ")
            sequence = seq_input.strip().upper() if seq_input.strip() else "ATCGATCGATCG"

            print(f"\n[PIPELINE START] Starting Genome Simulation -> Payload ID: {pay_id} | Sequence: '{sequence}'")
            workflow_res = await agent.execute_simulation_workflow(pay_id, sequence)

            print(f"\n[1. RAG POLICY GROUNDING]")
            print(f"  Grounded Policy: {workflow_res['rag_grounding']['grounding_text']}")

            print("\n[2. SIMULATION RESULT]")
            print(workflow_res["server_response"])

            print(f"\n[3. DYNAMIC CONTEXT MANAGEMENT (Observation Masking Active)]")
            print(f"  Managed Context Window contains {workflow_res['managed_context']['buffer_count']} turns.")
            print(f"  Downstream LLM Context Messages: {len(workflow_res['post_tool_llm_messages'])} (Bulky JSON suppressed)")

        elif choice == "3":
            print("\n--- QUERY BIOSAFETY POLICY KNOWLEDGE BASE (RAG) ---")
            query_input = await loop.run_in_executor(None, input, "Enter search query [e.g., 'Protocol 4.2b cardiac sedation']: ")
            query_text = query_input.strip() or "Protocol 4.2b cardiac risk screening"

            print(f"\nExecuting Hybrid (Vector + BM25) & Agentic RAG for: '{query_text}'...")
            rag_output = agent.retrieve_policy_grounding(query_text, update_scratchpad=True)

            print(f"\n[Hybrid RAG Top Matches]:")
            for idx, match in enumerate(rag_output["hybrid_matches"], 1):
                print(f"  {idx}. {match}")

            print(f"\n[Agentic RAG Verification Status]: {rag_output['agentic_result'].get('status')}")
            print(f"  Verified Context: {rag_output['agentic_result'].get('context')}")
            print(f"  (Scratchpad safety constraints updated with verified policy grounding)")

        elif choice == "4":
            print("\n" + "-" * 65)
            print(" ACTIVE MEMORY & CONTEXT DASHBOARD")
            print("-" * 65)

            ctx = agent.get_managed_context_window()
            sp = ctx["scratchpad"]
            print(f"1. SCRATCHPAD WORKING STATE:")
            print(f"   Current Plan:        {sp['current_plan']}")
            print(f"   Active Subgoal:      {sp['active_subgoal']}")
            print(f"   Working Variables:   {sp['working_variables']}")
            print(f"   Safety Constraints:  {sp['safety_constraints']}")

            print(f"\n2. MANAGED TRANSCRIPT BUFFER ({ctx['buffer_count']}/{ctx['max_buffer_size']} turns, Strategy: {ctx['strategy_applied']}):")
            for msg in ctx["active_transcript"]:
                role = msg.get("role", "unknown").upper()
                text = str(msg.get("content", ""))[:85].replace("\n", " ")
                print(f"   Turn {msg.get('turn_id', '?')} [{role}]: {text}...")

            print("\n3. ACTIVE CONSOLIDATED SEMANTIC FACTS:")
            facts = agent.semantic_store.list_all_active_facts()
            if not facts:
                print("   (No active semantic facts consolidated yet)")
            for f in facts:
                print(f"   * Fact '{f.fact_key}' -> Value: '{f.value}' (v{f.version}, confidence: {f.confidence})")

            print("\n4. RECENT ROUTER DECISION AUDIT LOG:")
            history = agent.router.get_decision_history(limit=5)
            if not history:
                print("   (No overflow decisions logged yet)")
            for h in history:
                print(f"   * [{h['decision']}] Summary: {h['item_summary'][:60]} | Reason: {h['reasoning']}")

        elif choice == "5":
            print("\n--- TEST CONTEXT WINDOW PRUNING STRATEGIES ---")
            print("Select Strategy to apply on current transcript:")
            print("  1: Sliding Window")
            print("  2: Observation & Tool Output Masking")
            print("  3: Recursive Summarization")
            print("  4: Zone-Based Pruning")

            strat_input = await loop.run_in_executor(None, input, "Enter choice (1-4) [default: 2]: ")
            strat_choice = strat_input.strip()
            strat_name = "observation_masking"
            if strat_choice == "1": strat_name = "sliding_window"
            elif strat_choice == "3": strat_name = "recursive_summarization"
            elif strat_choice == "4": strat_name = "zone_based_pruning"

            managed = agent.get_managed_context_window(strategy=strat_name)
            llm_msgs = agent.build_managed_context_for_llm(strategy=strat_name)
            print(f"\n[STRATEGY RESULT: '{strat_name}']")
            print(f"Original Count: {managed['original_count']} -> Managed Count: {managed['buffer_count']}")
            print(f"LLM Prompt Message Zones Generated: {len(llm_msgs)}")
            for idx, (role, text) in enumerate(llm_msgs, 1):
                clean_text = str(text)[:90].replace("\n", " ")
                print(f"  {idx}. [{role.upper()}]: {clean_text}")

        elif choice == "6":
            print("\n--- FREE-FORM AGENT CHAT (CONTEXT-MANAGED) ---")
            user_msg = await loop.run_in_executor(None, input, "Enter your message: ")
            if user_msg.strip():
                chat_res = agent.chat_turn(user_msg.strip())
                print(f"\n[Agent Response via {chat_res['strategy_used']}]:")
                print(chat_res["response"])
                print(f"(Managed Context Zones: {chat_res['managed_messages_count']})")

        elif choice == "7":
            print("\n--- TRIGGERING PERIODIC SEMANTIC CONSOLIDATION PASS ---")
            cons_res = agent.consolidation.run_consolidation_pass()
            print(f"Consolidation Pass Status:      {cons_res['status']}")
            print(f"Episodes Processed:            {cons_res.get('episodes_processed', 0)}")
            print(f"Facts Updated:                 {cons_res.get('facts_updated', 0)}")
            print(f"Conflicts / Contradictions:   {cons_res.get('conflicts_resolved', 0)}")

        else:
            print("Invalid choice. Please enter a number between 1 and 8.")


async def run_automated_demo(agent: VelloraAgent):
    print("\n" + "=" * 65)
    print(" VELLORA BIO - FULLY INTEGRATED AGENT DEMO")
    print(" Demonstrating Live RAG Grounding, Context Management & Reasoning")
    print("=" * 65)

    print("\n" + "-" * 65)
    print(" PHASE 1: RAG Biosafety Policy Grounding (Protocol 4.2b)")
    print("-" * 65)
    rag_info = agent.retrieve_policy_grounding("Protocol 4.2b cardiac risk screening")
    print(f"  Query: 'Protocol 4.2b cardiac risk screening'")
    print(f"  Hybrid RAG Retrieval Match:")
    print(f"   -> \"{rag_info['grounding_text']}\"")
    print(f"  Agentic RAG Status: {rag_info['agentic_result'].get('status').upper()}")
    print(f"  Scratchpad Constraints Updated: {agent.scratchpad.safety_constraints}")

    print("\n" + "-" * 65)
    print(" PHASE 2: Grounded Off-Target Simulation (Bulky Tool JSON & Masking)")
    print("-" * 65)
    sim_res = await agent.execute_simulation_workflow(payload_id=1, sequence="ATCGATCGATCG", session_id="auto_demo")
    print("  Simulation Output:")
    print(sim_res["server_response"])
    print(f"  Dynamic Context Strategy Applied: {sim_res['managed_context']['strategy_applied']}")
    print(f"  Context Window Turn Count: {sim_res['managed_context']['buffer_count']}")
    print(f"  Downstream LLM Context Zones: {len(sim_res['post_tool_llm_messages'])} (Bulky JSON suppressed via apply_context_strategy)")

    print("\n" + "-" * 65)
    print(" PHASE 3: Defensive Tool Design & BSL Authorization")
    print("-" * 65)
    print("Case A: Authorized Job (Dr. David Banner BSL-4 >= Tier 1):")
    auth_res = await agent.execute_synthesis_workflow(researcher_id=4, payload_id=1, sequence="ATCGATCG", session_id="auto_demo")
    print("  Agent LLM Reasoning: " + auth_res["agent_thought"])
    print("  Authorization Output:")
    print(auth_res["server_response"])

    print("\nCase B: Low Clearance Rejection (Dr. Alice Vance BSL-1 < Tier 4):")
    rej_res = await agent.execute_synthesis_workflow(researcher_id=1, payload_id=4, sequence="ATCGATCG", session_id="auto_demo")
    print("  Defensive Security Rejection Output:")
    print(rej_res["server_response"])

    print("\n" + "-" * 65)
    print(" PHASE 4: Memory Buffer Overflow & Promote-or-Drop Router")
    print("-" * 65)
    all_decisions = rej_res["user_overflow_decisions"] + rej_res["tool_overflow_decisions"]
    print(f"  Buffer Overflow Processed {len(all_decisions)} Aging Items:")
    for d in all_decisions:
        print(f"   -> ROUTER DECISION: [{d.decision}] | Reason: {d.reasoning}")

    print("\n" + "-" * 65)
    print(" PHASE 5: Semantic Memory Consolidation & Conflict Resolution")
    print("-" * 65)
    cons_res = agent.consolidation.run_consolidation_pass()
    print(f"  Consolidation Pass Executed -> Facts Updated: {cons_res['facts_updated']}, Conflicts Resolved: {cons_res['conflicts_resolved']}")
    active_facts = agent.semantic_store.list_all_active_facts()
    print("  Active Consolidated Semantic Facts:")
    for f in active_facts:
        print(f"   * [{f.fact_key}] -> Value: '{f.value}' (Version {f.version})")

    print("\n" + "-" * 65)
    print(" PHASE 6: Dynamic Context Management Prompt Assembly (4-Zones)")
    print("-" * 65)
    managed_llm_messages = agent.build_managed_context_for_llm(strategy="observation_masking")
    print(f"  Constructed 4-Zone LLM Prompt Messages ({len(managed_llm_messages)} zones/turns):")
    for idx, (role, content) in enumerate(managed_llm_messages, 1):
        content_preview = str(content)[:80].replace("\n", " ")
        print(f"   {idx}. [{role.upper()}]: {content_preview}...")

    print("\n" + "=" * 65)
    print(" FULLY INTEGRATED AGENT PIPELINE DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vellora Bio MCP Client Agent with Integrated RAG, Context Management & Memory")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport mode to connect")
    parser.add_argument("--url", default="http://127.0.0.1:8000/sse", help="SSE Endpoint URL")
    parser.add_argument("--auto", action="store_true", help="Run automated demo test cases non-interactively")
    args = parser.parse_args()

    asyncio.run(run_agent(transport=args.transport, sse_url=args.url, interactive=not args.auto))
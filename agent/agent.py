import argparse
import asyncio
import json
import os
import sys

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
from memory.episodic_store import EpisodicStore
from memory.semantic_store import SemanticStore
from memory.router import PromoteOrDropRouter
from memory.consolidation import SemanticConsolidationEngine
from context_eval.strategies import apply_context_strategy
from rag.vector_store import VectorStoreManager
from rag.hybrid_rag import HybridRAG
from rag.agentic_rag import AgenticRAG
from mcp_server.server import process_mcp_protocol_request


class Agent:
    def __init__(self):
        self.vector_store = VectorStoreManager()
        self.hybrid_rag = HybridRAG(self.vector_store, ["Vellora biosafety protocol v2.1"])
        self.agentic_rag = AgenticRAG(self.hybrid_rag)

    def execute_rag_pipeline(self, user_query: str):
        """Executes server protocol request and verified agentic RAG pipeline."""
        mcp_req = json.dumps({"method": "mcp/rag/query", "params": {"query": user_query}, "id": 101})
        protocol_res = process_mcp_protocol_request(mcp_req)
        rag_res = self.agentic_rag.retrieve_and_verify(user_query)
        return {"protocol_response": json.loads(protocol_res), "rag_result": rag_res}


VelloraAgent = Agent


async def run_agent(transport: str = "stdio", sse_url: str = "http://127.0.0.1:8000/sse", interactive: bool = True):
    print("=" * 65)
    print(f" VELLORA BIO - MCP AGENT (Transport: {transport.upper()})")
    print(" Includes Long-Term Memory Architecture & Context Window Engine")
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
    
    capabilities = initialize_result.capabilities
    has_tools = capabilities.tools is not None if hasattr(capabilities, 'tools') else True

    if not has_tools:
        print("  WARNING: Server does not declare tool capabilities! Aborting tool operations.")
        return

    print("\n[3] Discovering Available Tools from Server...")
    tools_response = await session.list_tools()
    print(f"  Discovered {len(tools_response.tools)} Registered Tools:")
    for tool in tools_response.tools:
        print(f"     * Tool: {tool.name} -> {tool.description[:70]}...")

    # Initialize Person 2 Memory Systems
    scratchpad = Scratchpad(
        current_plan="Interactive Gene Synthesis & Biosafety Tracking Session",
        active_subgoal="Initializing memory system",
        working_variables={},
        safety_constraints=["BSL clearance must satisfy target Risk Tier"]
    )
    short_term_mem = ShortTermMemory(max_buffer_size=4, scratchpad=scratchpad)
    episodic_store = EpisodicStore()
    semantic_store = SemanticStore()
    router = PromoteOrDropRouter(episodic_store=episodic_store)
    consolidation_engine = SemanticConsolidationEngine(episodic_store=episodic_store, semantic_store=semantic_store)

    memory_sys = {
        "scratchpad": scratchpad,
        "short_term": short_term_mem,
        "episodic": episodic_store,
        "semantic": semantic_store,
        "router": router,
        "consolidation": consolidation_engine,
    }

    if not interactive:
        await run_automated_demo(session, memory_sys)
        return

    await run_interactive_mode(session, memory_sys)

async def run_interactive_mode(session: ClientSession, memory_sys: dict):
    print("\n" + "=" * 65)
    print(" VELLORA BIO - INTERACTIVE TERMINAL (MEMORY SYSTEM ACTIVE)")
    print("=" * 65)

    loop = asyncio.get_event_loop()
    short_term = memory_sys["short_term"]
    scratchpad = memory_sys["scratchpad"]
    router = memory_sys["router"]
    consolidation = memory_sys["consolidation"]
    semantic_store = memory_sys["semantic"]

    session_id = "interactive_sess_01"

    while True:
        print("\nSelect an action:")
        print("  1: Submit Synthesis Job (Records turn, updates Scratchpad, triggers Router)")
        print("  2: Run Off-Target Simulation (Updates Scratchpad, records turn)")
        print("  3: View Active Memory State (Scratchpad, Buffer, Facts, Router Audit)")
        print("  4: Run Context Window Management Pruning Strategy (Test 4 Strategies)")
        print("  5: Trigger Periodic Semantic Memory Consolidation Pass")
        print("  6: Exit")
        
        choice = await loop.run_in_executor(None, input, "\nEnter choice (1-6): ")
        choice = choice.strip()

        if choice == "6" or choice.lower() == "exit":
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

            scratchpad.update_subgoal("Submitting synthesis job and checking authorization")
            scratchpad.set_variable("researcher_id", res_id)
            scratchpad.set_variable("payload_id", pay_id)
            scratchpad.set_variable("sequence", sequence)

            print(f"\nSubmitting Job -> Researcher ID: {res_id} | Payload ID: {pay_id} | Sequence: '{sequence}'")
            
            # Record user turn in short term memory
            pruned_user = short_term.add_message("user", f"Submit job for researcher={res_id}, payload={pay_id}, seq={sequence}")
            if pruned_user:
                decisions = router.process_overflow(pruned_user, session_id=session_id, researcher_id=res_id)
                print(f"  [ROUTER OVERFLOW] Pruned {len(pruned_user)} items -> Evaluated by Router!")

            try:
                result = await session.call_tool("submit_synthesis_job", {
                    "researcher_id": res_id,
                    "payload_id": pay_id,
                    "sequence": sequence
                })
                resp_text = result.content[0].text if result.content else str(result)
                print("\nSERVER RESPONSE:")
                print(resp_text)

                # Record tool response in short term memory
                pruned_tool = short_term.add_message(
                    "tool",
                    resp_text,
                    {"tool_name": "submit_synthesis_job", "researcher_id": res_id, "payload_id": pay_id}
                )
                if pruned_tool:
                    decisions = router.process_overflow(pruned_tool, session_id=session_id, researcher_id=res_id)
                    print(f"  [ROUTER OVERFLOW] Pruned {len(pruned_tool)} items -> Evaluated by Router!")

                # Run automatic consolidation pass
                cons_res = consolidation.run_consolidation_pass()
                if cons_res.get("facts_updated", 0) > 0:
                    print(f"  [CONSOLIDATION PASS] Updated {cons_res['facts_updated']} facts! (Conflicts resolved: {cons_res['conflicts_resolved']})")

            except Exception as e:
                print(f"\nERROR: {e}")

        elif choice == "2":
            print("\n--- RUN SAFETY SIMULATION ---")
            pay_input = await loop.run_in_executor(None, input, "Enter Payload ID (1-4) [default: 1]: ")
            pay_id = int(pay_input.strip()) if pay_input.strip().isdigit() else 1

            seq_input = await loop.run_in_executor(None, input, "Enter DNA Sequence [default: ATCGATCGATCG]: ")
            sequence = seq_input.strip().upper() if seq_input.strip() else "ATCGATCGATCG"

            scratchpad.update_subgoal("Executing genome-wide off-target alignment simulation")
            scratchpad.set_variable("payload_id", pay_id)
            scratchpad.set_variable("sequence", sequence)

            print(f"\nStarting Genome Simulation -> Payload ID: {pay_id} | Sequence: '{sequence}'")
            
            pruned_user = short_term.add_message("user", f"Run simulation for payload={pay_id}, seq={sequence}")
            if pruned_user:
                router.process_overflow(pruned_user, session_id=session_id)

            try:
                result = await session.call_tool("simulate_off_target_effects", {
                    "payload_id": pay_id,
                    "sequence": sequence
                })
                resp_text = result.content[0].text if result.content else str(result)
                print("\nSIMULATION RESULT:")
                print(resp_text)

                pruned_tool = short_term.add_message("tool", resp_text, {"tool_name": "simulate_off_target_effects"})
                if pruned_tool:
                    router.process_overflow(pruned_tool, session_id=session_id)

            except Exception as e:
                print(f"\nERROR: {e}")

        elif choice == "3":
            print("\n" + "-" * 65)
            print(" ACTIVE MEMORY STATE DASHBOARD")
            print("-" * 65)
            
            ctx = short_term.get_working_context()
            sp = ctx["scratchpad"]
            print(f"1. SCRATCHPAD STATE (Plan & Subgoal):")
            print(f"   Current Plan:    {sp['current_plan']}")
            print(f"   Active Subgoal:  {sp['active_subgoal']}")
            print(f"   Variables:       {sp['working_variables']}")
            print(f"   Constraints:     {sp['safety_constraints']}")

            print(f"\n2. ROLLING SHORT-TERM BUFFER ({ctx['buffer_count']}/{ctx['max_buffer_size']} turns):")
            for msg in ctx["active_transcript"]:
                role = msg["role"].upper()
                text = str(msg["content"])[:70].replace("\n", " ")
                print(f"   Turn {msg['turn_id']} [{role}]: {text}...")

            print("\n3. ACTIVE SEMANTIC FACTS:")
            facts = semantic_store.list_all_active_facts()
            if not facts:
                print("   (No active semantic facts consolidated yet)")
            for f in facts:
                print(f"   * Fact '{f.fact_key}' -> Value: '{f.value}' (v{f.version}, confidence: {f.confidence})")

            print("\n4. RECENT ROUTER DECISION AUDIT LOG:")
            history = router.get_decision_history(limit=5)
            if not history:
                print("   (No overflow decisions logged yet)")
            for h in history:
                print(f"   * [{h['decision']}] Summary: {h['item_summary'][:60]} | Reason: {h['reasoning']}")

        elif choice == "4":
            print("\n--- CONTEXT WINDOW MANAGEMENT PRUNING STRATEGIES ---")
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

            pruned_transcript = apply_context_strategy(short_term.buffer, strat_name)
            print(f"\n[STRATEGY RESULT: '{strat_name}']")
            print(f"Original Turn Count: {len(short_term.buffer)} -> Pruned Count: {len(pruned_transcript)}")
            for idx, msg in enumerate(pruned_transcript, 1):
                role = msg.get("role", "unknown").upper()
                text = str(msg.get("content", ""))[:90].replace("\n", " ")
                print(f"  {idx}. [{role}]: {text}")

        elif choice == "5":
            print("\n--- TRIGGERING PERIODIC SEMANTIC CONSOLIDATION PASS ---")
            cons_res = consolidation.run_consolidation_pass()
            print(f"Consolidation Pass Status:      {cons_res['status']}")
            print(f"Episodes Processed:            {cons_res.get('episodes_processed', 0)}")
            print(f"Facts Updated:                 {cons_res.get('facts_updated', 0)}")
            print(f"Conflicts / Contradictions:   {cons_res.get('conflicts_resolved', 0)}")

        else:
            print("Invalid choice. Please enter a number between 1 and 6.")

async def run_automated_demo(session: ClientSession, memory_sys: dict):
    short_term = memory_sys["short_term"]
    scratchpad = memory_sys["scratchpad"]
    router = memory_sys["router"]
    consolidation = memory_sys["consolidation"]
    semantic_store = memory_sys["semantic"]

    print("\n" + "=" * 65)
    print(" VELLORA BIO - AUTOMATED DEMO WITH MEMORY & CONTEXT SYSTEM")
    print("=" * 65)

    print("\n" + "-" * 65)
    print(" CONCERN 1: Progress Tracking (simulate_off_target_effects)")
    print("-" * 65)
    
    scratchpad.update_subgoal("Running off-target safety simulation for payload 1")
    sim_result = await session.call_tool("simulate_off_target_effects", {
        "payload_id": 1,
        "sequence": "ATCGATCGATCG"
    })
    resp1 = sim_result.content[0].text if sim_result.content else str(sim_result)
    print("  Simulation Output:")
    print(resp1)

    # Record in short-term memory
    short_term.add_message("user", "Run simulation for payload 1 sequence ATCGATCGATCG")
    short_term.add_message("tool", resp1, {"tool_name": "simulate_off_target_effects"})

    print("\n" + "-" * 65)
    print(" CONCERN 2: Defensive Tool Design (submit_synthesis_job)")
    print("-" * 65)

    print("Case A: Submitting Synthesis Job (Researcher BSL-4 >= Payload Risk Tier 1):")
    scratchpad.update_subgoal("Submitting BSL-4 authorized job")
    job_result = await session.call_tool("submit_synthesis_job", {
        "researcher_id": 4,
        "payload_id": 1,
        "sequence": "ATCGATCG"
    })
    resp2 = job_result.content[0].text if job_result.content else str(job_result)
    print("  Authorization Success Output:")
    print(resp2)

    short_term.add_message("user", "Submit synthesis job for researcher=4 payload=1")
    short_term.add_message("tool", resp2, {"tool_name": "submit_synthesis_job"})

    print("\nCase B: Submitting Synthesis Job with Low Clearance (Researcher BSL-1 < Risk Tier 4):")
    scratchpad.update_subgoal("Testing low clearance rejection")
    rej_result = await session.call_tool("submit_synthesis_job", {
        "researcher_id": 1,
        "payload_id": 4,
        "sequence": "ATCGATCG"
    })
    resp3 = rej_result.content[0].text if rej_result.content else str(rej_result)
    print("  Defensive Security Rejection Output:")
    print(resp3)

    # Adding messages will trigger short term buffer overflow (max 4)
    pruned_msgs = short_term.add_message("user", "Submit synthesis job for researcher=1 payload=4")
    if pruned_msgs:
        print(f"\n  [MEMORY OVERFLOW TRIGGERED] Buffer exceeded max_buffer_size(4). Pruned {len(pruned_msgs)} items.")
        decisions = router.process_overflow(pruned_msgs, session_id="auto_demo", researcher_id=1)
        for d in decisions:
            print(f"   -> ROUTER DECISION: [{d.decision}] | Reason: {d.reasoning}")

    print("\n" + "-" * 65)
    print(" CONCERN 3: Semantic Memory Consolidation & Contradiction Resolution")
    print("-" * 65)

    cons_res = consolidation.run_consolidation_pass()
    print(f"  Consolidation Pass Executed -> Facts Updated: {cons_res['facts_updated']}, Conflicts Resolved: {cons_res['conflicts_resolved']}")
    
    active_facts = semantic_store.list_all_active_facts()
    print("\n  Active Consolidated Semantic Facts:")
    for f in active_facts:
        print(f"   * [{f.fact_key}] -> Value: '{f.value}' (Version {f.version})")

    print("\n" + "-" * 65)
    print(" CONCERN 4: Context Window Strategy Execution")
    print("-" * 65)

    masked_transcript = apply_context_strategy(short_term.buffer, "observation_masking")
    print(f"  Applied Observation Masking Strategy to Transcript ({len(masked_transcript)} turns):")
    for idx, msg in enumerate(masked_transcript, 1):
        print(f"   {idx}. [{msg['role'].upper()}]: {str(msg['content'])[:80]}...")

    print("\nAUTOMATED DEMO WITH MEMORY & CONTEXT MANAGEMENT COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vellora Bio MCP Client Agent with Long-Term Memory")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport mode to connect")
    parser.add_argument("--url", default="http://127.0.0.1:8000/sse", help="SSE Endpoint URL")
    parser.add_argument("--auto", action="store_true", help="Run automated demo test cases non-interactively")
    args = parser.parse_args()

    asyncio.run(run_agent(transport=args.transport, sse_url=args.url, interactive=not args.auto))
import argparse
import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def run_agent(transport: str = "stdio", sse_url: str = "http://127.0.0.1:8000/sse", interactive: bool = True):
    print("=" * 60)
    print(f" VELLORA BIO - MCP AGENT (Transport: {transport.upper()})")
    print("=" * 60)

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

    if not interactive:
        await run_automated_demo(session)
        return

    await run_interactive_mode(session)

async def run_interactive_mode(session: ClientSession):
    print("\n" + "=" * 60)
    print(" 🧪 VELLORA BIO - INTERACTIVE TERMINAL")
    print("=" * 60)

    loop = asyncio.get_event_loop()

    while True:
        print("\nSelect an action:")
        print("  1: Submit Synthesis Job (Test BSL Clearance & Security)")
        print("  2: Run Off-Target Genome Safety Simulation (Test Progress Tracking)")
        print("  3: Exit")
        
        choice = await loop.run_in_executor(None, input, "\nEnter choice (1, 2, or 3): ")
        choice = choice.strip()

        if choice == "3" or choice.lower() == "exit":
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

            print(f"\nSubmitting Job -> Researcher ID: {res_id} | Payload ID: {pay_id} | Sequence: '{sequence}'")
            try:
                result = await session.call_tool("submit_synthesis_job", {
                    "researcher_id": res_id,
                    "payload_id": pay_id,
                    "sequence": sequence
                })
                print("\nSERVER RESPONSE:")
                print(result.content[0].text if result.content else result)
            except Exception as e:
                print(f"\nERROR: {e}")

        elif choice == "2":
            print("\n--- RUN SAFETY SIMULATION ---")
            pay_input = await loop.run_in_executor(None, input, "Enter Payload ID (1-4) [default: 1]: ")
            pay_id = int(pay_input.strip()) if pay_input.strip().isdigit() else 1

            seq_input = await loop.run_in_executor(None, input, "Enter DNA Sequence [default: ATCGATCGATCG]: ")
            sequence = seq_input.strip().upper() if seq_input.strip() else "ATCGATCGATCG"

            print(f"\nStarting Genome Simulation -> Payload ID: {pay_id} | Sequence: '{sequence}'")
            try:
                result = await session.call_tool("simulate_off_target_effects", {
                    "payload_id": pay_id,
                    "sequence": sequence
                })
                print("\nSIMULATION RESULT:")
                print(result.content[0].text if result.content else result)
            except Exception as e:
                print(f"\nERROR: {e}")
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

async def run_automated_demo(session: ClientSession):
    print("\n" + "-" * 60)
    print(" PROTOCOL CONCERN 1: Progress Tracking (simulate_off_target_effects)")
    print("-" * 60)
    
    sim_result = await session.call_tool("simulate_off_target_effects", {
        "payload_id": 1,
        "sequence": "ATCGATCGATCG"
    })
    print("  Simulation Output:")
    print(sim_result.content[0].text if sim_result.content else sim_result)

    print("\n" + "-" * 60)
    print(" PROTOCOL CONCERN 2: Defensive Tool Design (submit_synthesis_job)")
    print("-" * 60)

    print("Case A: Submitting Synthesis Job (Researcher BSL-4 >= Payload Risk Tier 1):")
    job_result = await session.call_tool("submit_synthesis_job", {
        "researcher_id": 4,
        "payload_id": 1,
        "sequence": "ATCGATCG"
    })
    print("  Authorization Success Output:")
    print(job_result.content[0].text if job_result.content else job_result)

    print("\nCase B: Submitting Synthesis Job with Low Clearance (Researcher BSL-1 < Risk Tier 4):")
    rej_result = await session.call_tool("submit_synthesis_job", {
        "researcher_id": 1,
        "payload_id": 4,
        "sequence": "ATCGATCG"
    })
    print("  Defensive Security Rejection Output:")
    print(rej_result.content[0].text if rej_result.content else rej_result)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vellora Bio MCP Client Agent")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport mode to connect")
    parser.add_argument("--url", default="http://127.0.0.1:8000/sse", help="SSE Endpoint URL")
    parser.add_argument("--auto", action="store_true", help="Run automated demo test cases non-interactively")
    args = parser.parse_args()

    asyncio.run(run_agent(transport=args.transport, sse_url=args.url, interactive=not args.auto))


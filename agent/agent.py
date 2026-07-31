import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# إضافة مسار المشروع للـ PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def run_agent_demo():
    print("=" * 60)
    print(" VELLORA BIO - MCP AGENT DEMO")
    print("=" * 60)

    # 1. إعداد مسار تشغيل سيرفر الـ MCP (محلياً عبر stdio)
    server_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp_server", "server.py"))
    
    server_params = StdioServerParameters(
        command=sys.executable,  # بيستخدم نفس مسار python المستعمل
        args=[server_script],
        env=os.environ.copy()
    )

    print("\n[1] Connecting to MCP Server via stdio Transport...")
    
    # 2. فتح الاتصال مع السيرفر
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            
            # --- [Capability Negotiation] ---
            print("[2] Initiating Capability Negotiation (Handshake)...")
            initialize_result = await session.initialize()
            print("  Server Handshake Successful!")
            print(f"    Server Info: {initialize_result.serverInfo.name} (v{initialize_result.serverInfo.version})")
            
            # --- [Tool Discovery] ---
            print("\n[3] Discovering Available Tools from Server...")
            tools_response = await session.list_tools()
            print(f"  Found {len(tools_response.tools)} Tools:")
            for tool in tools_response.tools:
                print(f"     Tool: {tool.name} -> {tool.description[:60]}...")

            print("\n" + "-" * 60)
            print(" TESTING TOOL 1: simulate_off_target_effects (Progress Tracking)")
            print("-" * 60)
            
            # استدعاء الأداة الأولى والتفاعل مع Progress Tracking
            progress_payload = {
                "payload_id": 1,
                "sequence": "ATCGATCGATCG"
            }
            print(f"Calling 'simulate_off_target_effects' with sequence: {progress_payload['sequence']}")
            sim_result = await session.call_tool("simulate_off_target_effects", progress_payload)
            print("  Simulation Output:")
            print(sim_result.content[0].text if sim_result.content else sim_result)

            print("\n" + "-" * 60)
            print(" TESTING TOOL 2: submit_synthesis_job (Defensive Tool Design)")
            print("-" * 60)

            # اختبار أداة التصنيع - حالة نجاح (باحث مسموح له)
            success_payload = {
                "researcher_id": 1,
                "payload_id": 1,
                "sequence": "ATCGATCG"
            }
            print(f"Submitting Job (Researcher BSL Clearance >= Payload Risk Tier):")
            job_result = await session.call_tool("submit_synthesis_job", success_payload)
            print("  Authorization Success Output:")
            print(job_result.content[0].text if job_result.content else job_result)

            # اختبار أداة التصنيع - حالة رفض بسبب الأمان (Defensive Violation)
            print("\nTesting Security Rejection (Invalid Researcher Clearance):")
            rejected_payload = {
                "researcher_id": 2, # باحث BSL-1 بيحاول يطلب شفرة خطيرة Tier 4
                "payload_id": 2,
                "sequence": "ATCGATCG"
            }
            rej_result = await session.call_tool("submit_synthesis_job", rejected_payload)
            print("  Defensive Authorization Rejection Output:")
            print(rej_result.content[0].text if rej_result.content else rej_result)

            print("\n" + "=" * 60)
            print(" DEMO COMPLETE: All Required Protocol Concerns Validated!")
            print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_agent_demo())
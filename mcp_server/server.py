import sys
import os
import asyncio
import inspect
import importlib
from types import SimpleNamespace
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from mcp.server.fastmcp import FastMCP, Context
except ImportError:  # pragma: no cover - exercised in minimal test environments
    class Context:  # type: ignore[override]
        def info(self, message: str):
            return message

    class FastMCP:
        def __init__(self, name: str):
            self.name = name
            self.settings = SimpleNamespace(host="127.0.0.1", port=8000)
            self._tools = {}

        def tool(self, **kwargs):
            def decorator(func):
                self._tools[kwargs.get("name", func.__name__)] = func
                return func
            return decorator

        def run(self, transport: str = "stdio"):
            return None

from mcp_server.tools.defensive_synthesis import handle_submit_synthesis_job
from mcp_server.tools.progress_off_target import handle_simulate_off_target_effects
from mcp_server.registry import registry

mcp = FastMCP("Vellora Biosafety Server")

@mcp.tool(
    name="submit_synthesis_job",
    description="Submits a genetic sequence payload for automated laboratory synthesis after validating ATCG nucleotide schema and server-side BSL clearance authorization."
)
def submit_synthesis_job(
    researcher_id: int,
    payload_id: int,
    sequence: str
) -> Dict[str, Any]:
    """
    Args:
        researcher_id: Unique integer identifier of the submitting researcher (validated for BSL clearance level).
        payload_id: Unique integer identifier of the target genetic payload record.
        sequence: DNA nucleotide string consisting strictly of A, C, T, G characters.
    """
    return handle_submit_synthesis_job(
        researcher_id=researcher_id,
        payload_id=payload_id,
        sequence=sequence
    )

@mcp.tool(
    name="simulate_off_target_effects",
    description="Runs a long-running genome-wide off-target alignment simulation across 24 human chromosomes, emitting real-time progress notifications."
)
async def simulate_off_target_effects(
    payload_id: int,
    sequence: str,
    ctx: Context
) -> Dict[str, Any]:
    """
    Args:
        payload_id: Unique integer identifier of the target genetic payload.
        sequence: Genetic target sequence to evaluate for off-target binding risks.
    """
    progress_events = []

    def on_progress(current: int, total: int, message: str):
        progress_events.append(f"[{current}/{total}] {message}")

    result = await asyncio.to_thread(handle_simulate_off_target_effects,
        payload_id=payload_id,
        sequence=sequence,
        progress_callback=on_progress
    )
    for message in progress_events:
        notification = ctx.info(message)
        if inspect.isawaitable(notification):
            await notification
    return result


registry.register("submit_synthesis_job", submit_synthesis_job, "Submit a validated synthesis job")
registry.register("simulate_off_target_effects", simulate_off_target_effects, "Run an off-target safety simulation")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Vellora Bio MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode to run the server (stdio for local process, sse for Streamable HTTP remote service)"
    )
    parser.add_argument("--port", type=int, default=8000, help="Port to use when running in sse mode")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address when running in sse mode")
    args = parser.parse_args()

    if args.transport == "sse":
        print(f"Starting Vellora Biosafety MCP Server in Streamable HTTP (SSE) mode on http://{args.host}:{args.port}/sse ...")
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")

import json

def process_mcp_protocol_request(request_payload: str) -> str:
    """MCP Server-side protocol handling data access boundaries."""
    try:
        payload = json.loads(request_payload)
        method = payload.get("method")
        params = payload.get("params", {})
        agent_id = params.get("agent_id")

        if method == "mcp/tools/list":
            return json.dumps({"jsonrpc": "2.0", "result": {"tools": registry.list(agent_id)}, "id": payload.get("id", 1)})
        if method == "mcp/tools/register":
            name = params["name"]
            handler = params.get("handler")
            if handler is None and params.get("handler_path"):
                module_name, separator, attribute_name = params["handler_path"].rpartition(":")
                if not separator:
                    module_name, _, attribute_name = params["handler_path"].rpartition(".")
                if not module_name or not attribute_name:
                    raise ValueError("handler_path must use module:attribute notation")
                handler = getattr(importlib.import_module(module_name), attribute_name)
            if not callable(handler):
                raise ValueError("Runtime registration requires a callable handler or handler_path")
            registry.register(name, handler, params.get("description", ""), params.get("agents"), replace=params.get("replace", False))
            return json.dumps({"jsonrpc": "2.0", "result": {"registered": name}, "id": payload.get("id", 1)})
        if method == "mcp/tools/deregister":
            name = params["name"]
            return json.dumps({"jsonrpc": "2.0", "result": {"deregistered": registry.deregister(name)}, "id": payload.get("id", 1)})
        if method == "mcp/tools/call":
            registration = registry.get(params["name"], agent_id)
            result = registration.handler(**params.get("arguments", {}))
            if inspect.isawaitable(result):
                raise ValueError("Async tool calls must use the MCP transport")
            return json.dumps({"jsonrpc": "2.0", "result": result, "id": payload.get("id", 1)})
        
        if method == "mcp/rag/query":
            return json.dumps({
                "jsonrpc": "2.0",
                "result": {"status": "success", "query": params.get("query"), "protocol_version": "mcp-1.0"},
                "id": payload.get("id", 1)
            })
        if method == "mcp/planning/plan":
            from planning.decomposition import DecompositionEngine
            request = params.get("request", "")
            payload_id = params.get("payload_id")
            plan = DecompositionEngine().decompose(request, payload_id=payload_id)
            return json.dumps({
                "jsonrpc": "2.0",
                "result": {
                    "status": "success",
                    "plan": plan.model_dump(),
                    "execution_order": plan.execution_order(),
                    "protocol_version": "mcp-1.0",
                },
                "id": payload.get("id", 1),
            })
        if method == "mcp/planning/dynamic_plan":
            from planning.dynamic_decomposition import DynamicDecompositionEngine
            request = params.get("request", "")
            engine = DynamicDecompositionEngine()
            result = engine.run(request, executor=lambda task: {"task_id": task.id, "status": "ok"})
            return json.dumps({
                "jsonrpc": "2.0",
                "result": {"status": "success", "plan": result, "protocol_version": "mcp-1.0"},
                "id": payload.get("id", 1),
            })
        return json.dumps({"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}})
    except Exception as e:
        return json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}})
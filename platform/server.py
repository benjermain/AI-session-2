from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Dict, Optional

# Ensure workspace root is on sys.path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mcp_server.db_client import (
    get_db_connection,
    get_failure_ticket,
    get_latest_checkpoint,
    list_checkpoints,
    resolve_hitl_task,
)
import mcp_server.server  # Ensures default tools are registered
from mcp_server.registry import ToolRegistration, registry
from platform.dispatcher import dispatcher
from platform.llm_client import llm_client

app = FastAPI(
    title="Vellora Bio Agent Platform",
    description="Full-stack AI Agent Platform with State Graphs, Dynamic MCP Tool Management, RAG, and HITL/Failure Recovery",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# -----------------------------------------------------------------------------
# Request Models
# -----------------------------------------------------------------------------

class ChatRequest(BaseModel):
    agent_id: str
    message: str
    payload_id: int = 1
    researcher_id: int = 1
    sequence: str = "ATCGATCGATCG"
    thread_id: Optional[str] = None


class ToolToggleRequest(BaseModel):
    tool_name: str
    agent_id: str
    enabled: bool


class ToolRegisterRequest(BaseModel):
    name: str
    description: str
    handler_path: str
    agents: Optional[list[str]] = None


class RAGAddRequest(BaseModel):
    text: str
    source: str = "custom_policy"


class RAGTestRequest(BaseModel):
    query: str
    top_k: int = 3


class HITLResolveRequest(BaseModel):
    task_id: str
    approved: bool
    modified_state: Optional[Dict[str, Any]] = None


class TicketResolveRequest(BaseModel):
    ticket_id: str
    action: str = "retry"
    modified_state: Optional[Dict[str, Any]] = None


# -----------------------------------------------------------------------------
# Frontend Root Route
# -----------------------------------------------------------------------------

@app.get("/")
def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "Vellora Bio Platform API Active", "docs": "/docs"}


# -----------------------------------------------------------------------------
# Agent & Chat Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/agents")
def list_agents():
    return {"agents": dispatcher.list_agents()}


@app.post("/api/chat")
def execute_chat(req: ChatRequest):
    try:
        result = dispatcher.execute_agent(
            agent_id=req.agent_id,
            message=req.message,
            payload_id=req.payload_id,
            researcher_id=req.researcher_id,
            sequence=req.sequence,
            thread_id=req.thread_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def execute_chat_stream(req: ChatRequest):
    """Server-Sent Events (SSE) streaming endpoint for live execution visualization."""
    def event_generator():
        thread = req.thread_id or str(uuid.uuid4())
        yield f"data: {json.dumps({'event': 'start', 'agent_id': req.agent_id, 'thread_id': thread})}\n\n"

        try:
            # Yield step 1
            yield f"data: {json.dumps({'event': 'step', 'name': 'Validating Agent Manifest & Parameters', 'status': 'IN_PROGRESS'})}\n\n"
            
            result = dispatcher.execute_agent(
                agent_id=req.agent_id,
                message=req.message,
                payload_id=req.payload_id,
                researcher_id=req.researcher_id,
                sequence=req.sequence,
                thread_id=thread,
            )

            for step in result.get("steps", []):
                yield f"data: {json.dumps({'event': 'step', 'name': step['name'], 'status': step['status']})}\n\n"

            yield f"data: {json.dumps({'event': 'complete', 'result': result})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# -----------------------------------------------------------------------------
# Dynamic MCP Tool Management Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/admin/tools")
def list_admin_tools():
    """Lists all tools registered in the live MCP server and their per-agent permissions."""
    all_tools = registry.list()
    agents = dispatcher.list_agents()
    
    matrix = []
    for tool in all_tools:
        reg = registry.get(tool["name"])
        agent_perms = {}
        for ag in agents:
            ag_id = ag["id"]
            agent_perms[ag_id] = reg.agents is None or ag_id in reg.agents
        matrix.append({
            "name": tool["name"],
            "description": tool["description"],
            "permissions": agent_perms,
        })
    return {"tools": matrix, "agents": agents}


@app.post("/api/admin/tools/toggle")
def toggle_tool_permission(req: ToolToggleRequest):
    """Dynamically updates tool permissions for an agent on the live MCP server."""
    try:
        reg = registry.get(req.tool_name)
        current_agents = set(reg.agents) if reg.agents is not None else {a["id"] for a in dispatcher.list_agents()}
        
        if req.enabled:
            current_agents.add(req.agent_id)
        else:
            current_agents.discard(req.agent_id)

        # Replace registration with updated agent scope
        registry.register(
            name=reg.name,
            handler=reg.handler,
            description=reg.description,
            agents=current_agents,
            replace=True,
        )
        return {
            "status": "UPDATED",
            "tool_name": req.tool_name,
            "agent_id": req.agent_id,
            "enabled": req.enabled,
            "allowed_agents": list(current_agents),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/tools/register")
def register_runtime_tool(req: ToolRegisterRequest):
    """Registers a new tool into the MCP server dynamically."""
    try:
        module_name, func_name = req.handler_path.split(":")
        mod = __import__(module_name, fromlist=[func_name])
        handler = getattr(mod, func_name)

        item = registry.register(
            name=req.name,
            handler=handler,
            description=req.description,
            agents=req.agents,
            replace=True,
        )
        return {"status": "REGISTERED", "name": item.name, "description": item.description}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# Dynamic RAG Knowledge Base Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/admin/rag")
def list_rag_documents():
    docs = [{"id": str(i), "text": text, "source": "policy_manual"} for i, text in enumerate(dispatcher.rag_corpus)]
    return {"documents": docs, "total_count": len(docs)}


@app.post("/api/admin/rag")
def add_rag_document(req: RAGAddRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Document text cannot be empty")
    result = dispatcher.add_rag_document(req.text.strip(), source=req.source)
    return result


@app.delete("/api/admin/rag/{doc_id}")
def delete_rag_document(doc_id: str):
    result = dispatcher.delete_rag_document(doc_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/admin/rag/test")
def test_rag_query(req: RAGTestRequest):
    results = dispatcher.hybrid_rag.hybrid_search(req.query, top_k=req.top_k)
    return {"query": req.query, "results": results}


# -----------------------------------------------------------------------------
# HITL (Human-In-The-Loop) Escalation Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/admin/hitl")
def list_hitl_tasks():
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM hitl_tasks ORDER BY created_at DESC").fetchall()
    tasks = []
    for r in rows:
        item = dict(r)
        item["state"] = json.loads(item.pop("state_json"))
        tasks.append(item)
    return {"tasks": tasks}


@app.post("/api/admin/hitl/resolve")
def resolve_hitl_endpoint(req: HITLResolveRequest):
    try:
        decision = "APPROVED" if req.approved else "REJECTED"
        with get_db_connection() as conn:
            row = conn.execute("SELECT workflow, status FROM hitl_tasks WHERE id = ?", (req.task_id,)).fetchone()
            if row is None:
                raise KeyError(f"HITL task '{req.task_id}' not found")
            if row["status"] != "PENDING":
                raise ValueError(f"HITL task '{req.task_id}' is already {row['status']}")
            workflow_name = row["workflow"]

        resumed_result = None
        if workflow_name == "bioreactor_batch":
            resumed_result = dispatcher.wf_bioreactor.resume(req.task_id, req.approved, req.modified_state)
        elif workflow_name == "biosafety_escalation":
            resumed_result = dispatcher.wf_biosafety.resume(req.task_id, req.approved, req.modified_state)
        else:
            resolve_hitl_task(req.task_id, decision, req.modified_state)

        return {
            "status": "RESOLVED",
            "decision": decision,
            "task_id": req.task_id,
            "resumed_result": resumed_result,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# Failure Ticket Recovery Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/admin/tickets")
def list_failure_tickets():
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM failure_tickets ORDER BY created_at DESC").fetchall()
    tickets = []
    for r in rows:
        item = dict(r)
        item["state"] = json.loads(item.pop("state_json"))
        tickets.append(item)
    return {"tickets": tickets}


@app.post("/api/admin/tickets/resolve")
def resolve_ticket_endpoint(req: TicketResolveRequest):
    try:
        ticket = get_failure_ticket(req.ticket_id)
        if ticket["status"] != "OPEN":
            raise ValueError("Ticket is already resolved")

        state = req.modified_state or ticket["state"]
        workflow_name = ticket["workflow"]

        # Resume execution from checkpointed state
        resumed_result = None
        if workflow_name == "bioreactor_batch":
            resumed_result = dispatcher.wf_bioreactor.run(state)
        elif workflow_name == "biosafety_escalation":
            resumed_result = dispatcher.wf_biosafety.run(state)
        elif workflow_name == "vector_redesign":
            resumed_result = dispatcher.wf_redesign.run(state)

        # Close ticket in database
        with get_db_connection() as conn:
            conn.execute("UPDATE failure_tickets SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (req.ticket_id,))
            conn.commit()

        return {
            "status": "RESOLVED",
            "ticket_id": req.ticket_id,
            "workflow": workflow_name,
            "resumed_result": resumed_result,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# Checkpoint History & Memory Dashboard Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/checkpoints/{thread_id}")
def get_thread_checkpoints(thread_id: str):
    history = list_checkpoints(thread_id)
    latest = get_latest_checkpoint(thread_id)
    return {"thread_id": thread_id, "latest": latest, "history": history}


@app.get("/api/memory/state")
def get_memory_state():
    return dispatcher.get_memory_dashboard_state()


@app.get("/api/stats")
def get_system_stats():
    with get_db_connection() as conn:
        hitl_count = conn.execute("SELECT COUNT(*) FROM hitl_tasks WHERE status = 'PENDING'").fetchone()[0]
        ticket_count = conn.execute("SELECT COUNT(*) FROM failure_tickets WHERE status = 'OPEN'").fetchone()[0]
        synthesis_count = conn.execute("SELECT COUNT(*) FROM synthesis_jobs").fetchone()[0]
        checkpoint_count = conn.execute("SELECT COUNT(*) FROM state_checkpoints").fetchone()[0]

    return {
        "registered_tools": len(registry.list()),
        "rag_documents": len(dispatcher.rag_corpus),
        "pending_hitl_tasks": hitl_count,
        "open_failure_tickets": ticket_count,
        "synthesis_jobs": synthesis_count,
        "state_checkpoints": checkpoint_count,
        "active_agents": len(dispatcher.list_agents()),
    }


class LLMConfigRequest(BaseModel):
    api_key: str
    provider: str = "gemini"


@app.get("/api/config/llm")
def get_llm_config():
    return {
        "configured": llm_client.is_configured(),
        "has_gemini_key": bool(llm_client.gemini_api_key),
        "key_preview": f"••••••••{llm_client.gemini_api_key[-4:]}" if llm_client.gemini_api_key and len(llm_client.gemini_api_key) > 4 else None,
    }


@app.post("/api/config/llm")
def update_llm_config(req: LLMConfigRequest):
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    result = llm_client.set_gemini_api_key(req.api_key)
    return result


def start_server(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    print(f"Starting Vellora Bio Platform Server on http://{host}:{port} ...")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()

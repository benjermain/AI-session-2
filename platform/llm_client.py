from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional
from dotenv import load_dotenv, set_key

# Load environment variables
ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(ENV_PATH)


class LLMClient:
    """
    Manages Gemini (and OpenAI) API client connections for dynamic conversational reasoning
    across all 5 specialized agents.
    """

    SYSTEM_PROMPTS = {
        "bioreactor_batch": (
            "You are the Vellora Bio Bioreactor Batch Synthesis AI Agent. You are an expert in automated "
            "biotechnology manufacturing, protein & viral vector expression, bioreactor sensor telemetry (pH, dissolved oxygen, temperature), "
            "and sterile harvesting protocols. When users ask questions or issue commands, provide clear, scientific explanations "
            "of the multi-phase incubation lifecycle, sterility tolerances, and task decomposition."
        ),
        "biosafety_escalation": (
            "You are the Vellora Bio Dual-Use Biosafety Escalation AI Agent. You are a senior biosafety officer "
            "specializing in IBC compliance, CDC/NIH dual-use research of concern (DURC) guidelines, and containment "
            "tier triage (BSL-1 through BSL-4). Explain your risk rationale clearly, reference relevant policies, "
            "and explain why human-in-the-loop sign-offs are enforced on high-risk payloads."
        ),
        "vector_redesign": (
            "You are the Vellora Bio Off-Target Vector Redesign AI Agent. You specialize in genetic sequence optimization, "
            "Language Agent Tree Search (LATS), Monte Carlo Tree Search for nucleotide mutations, and off-target risk reduction. "
            "Explain sequence alignments, mutation decisions, and safety threshold validations with precision."
        ),
        "memory_rag": (
            "You are the Vellora Bio Grounded Biosafety RAG & Memory AI Agent. You maintain long-term institutional memory "
            "using rolling scratchpads, episodic interaction histories, and semantic fact consolidation. Always ground your "
            "answers in retrieved protocol documents and cite relevant policy clauses."
        ),
        "decomposition_planning": (
            "You are the Vellora Bio DAG Task Decomposition & Planning AI Agent. You analyze complex laboratory synthesis "
            "and validation objectives, deconstructing them into directed acyclic dependency graphs with topological ordering "
            "and dynamic replanning capabilities. Explain task breakdowns and contingency plans clearly."
        ),
    }

    def __init__(self):
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self._gemini_client = None
        self._init_client()

    def _init_client(self):
        if self.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Google GenAI client: {e}")
                self._gemini_client = None

    def is_configured(self) -> bool:
        return bool(self.gemini_api_key and self._gemini_client)

    def set_gemini_api_key(self, api_key: str) -> Dict[str, Any]:
        """Sets and persists the Gemini API key into .env and runtime client."""
        cleaned_key = api_key.strip()
        os.environ["GEMINI_API_KEY"] = cleaned_key
        self.gemini_api_key = cleaned_key

        # Persist to .env file
        try:
            if not os.path.exists(ENV_PATH):
                with open(ENV_PATH, "w", encoding="utf-8") as f:
                    f.write(f"GEMINI_API_KEY={cleaned_key}\n")
            else:
                set_key(ENV_PATH, "GEMINI_API_KEY", cleaned_key)
        except Exception as e:
            print(f"Notice: Could not write to .env file: {e}")

        self._init_client()
        return {"status": "SUCCESS", "configured": self.is_configured()}

    def generate_agent_response(
        self,
        agent_id: str,
        user_message: str,
        execution_data: Optional[Dict[str, Any]] = None,
        retrieved_context: Optional[list] = None,
        scratchpad: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Calls Gemini API with the agent's persona, retrieved policies, and execution telemetry
        to generate a conversational and informative response.
        """
        system_persona = self.SYSTEM_PROMPTS.get(agent_id, "You are a helpful biotechnology AI assistant.")
        
        # Build structured context block
        context_sections = []
        if retrieved_context:
            context_sections.append("### Retrieved Biosafety Policies / Protocols:\n" + "\n".join(f"- {c}" for c in retrieved_context))
        
        if scratchpad:
            context_sections.append(
                f"### Active Scratchpad Memory:\n"
                f"- Working Plan: {scratchpad.get('current_plan', 'None')}\n"
                f"- Active Subgoal: {scratchpad.get('active_subgoal', 'None')}\n"
                f"- Safety Constraints: {', '.join(scratchpad.get('safety_constraints', []))}"
            )

        if execution_data:
            context_sections.append(f"### Underlying Execution Telemetry & State:\n```json\n{execution_data}\n```")

        context_str = "\n\n".join(context_sections)

        prompt = f"""{system_persona}

{context_str}

User Prompt:
"{user_message}"

Instructions:
1. Provide a comprehensive, professional, and conversational response addressing the user's prompt directly.
2. Incorporate the execution telemetry, status (e.g. COMPLETED, PAUSED, SAFE), and retrieved policy context naturally.
3. If an action was paused for human approval (HITL) or triggered a failure ticket, clearly explain why and what the next steps are.
4. Format using clear markdown headings, bullet points, and code blocks where appropriate.
"""

        # If Gemini client is active and configured, make the live API call
        if self.is_configured() and self._gemini_client:
            try:
                # Try modern models in order of preference
                for model_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                    try:
                        response = self._gemini_client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                        )
                        if response and response.text:
                            return response.text
                    except Exception as model_err:
                        print(f"Model {model_name} attempt failed: {model_err}, trying fallback...")
                        continue
            except Exception as e:
                print(f"Gemini API generation error: {e}")

        # Fallback informative synthesizer if no API key is set
        return self._generate_offline_synthesis(agent_id, user_message, execution_data, retrieved_context)

    def _generate_offline_synthesis(
        self,
        agent_id: str,
        user_message: str,
        execution_data: Optional[Dict[str, Any]] = None,
        retrieved_context: Optional[list] = None,
    ) -> str:
        """Generates a rich, contextual response when operating in offline/demo mode."""
        status = execution_data.get("status", "COMPLETED") if execution_data else "COMPLETED"

        if agent_id == "bioreactor_batch":
            if status == "PAUSED":
                return (
                    f"### 🧬 Bioreactor Batch Processing: Paused at Sterility Gate\n\n"
                    f"The bioreactor synthesis recipe has been decomposed into validated subtasks and loaded into Vessel #1. "
                    f"Multi-cycle sensor telemetry (pH: 7.32, DO: 44.5%, Temp: 37.0°C) was recorded across incubation cycles.\n\n"
                    f"> **Action Required:** The workflow has reached the **Technician Sterility Sign-Off Gate** (Task ID `{execution_data.get('task_id')}`). "
                    f"Please navigate to the **HITL Approvals** tab to inspect the sterility assay readings and approve the harvest."
                )
            else:
                return (
                    f"### 🧬 Bioreactor Batch Synthesis Complete\n\n"
                    f"Successfully processed batch for payload #{execution_data.get('payload_id', 1)}. "
                    f"Harvest yielded **{execution_data.get('harvest_yield_mg_l', 520)} mg/L** at **{execution_data.get('purity_pct', 98.4)}% purity** with all sensor parameters within clinical specifications."
                )

        elif agent_id == "biosafety_escalation":
            if status == "PAUSED":
                return (
                    f"### 🛡️ Dual-Use Biosafety Triage: IBC Review Required\n\n"
                    f"The submitted sequence was triaged under **Risk Tier {execution_data.get('state', {}).get('risk_tier', 3)}** guidelines. "
                    f"Constrained ReAct diagnostics and Tree of Thoughts pathways flagged potential dual-use biological concerns.\n\n"
                    f"> **Escalation:** Paused at Institutional Biosafety Committee Gate (Task `{execution_data.get('task_id')}`). "
                    f"An authorized IBC administrator must approve this payload before laboratory synthesis can proceed."
                )
            else:
                return (
                    f"### 🛡️ Dual-Use Biosafety Clearance Granted\n\n"
                    f"The submitted genetic payload was screened against CDC/NIH dual-use databases and IBC policy manuals. "
                    f"All constrained ReAct diagnostic checks passed successfully with zero quarantine flags."
                )

        elif agent_id == "vector_redesign":
            if status == "SAFE":
                return (
                    f"### 🧪 Off-Target Vector Redesign Succeeded\n\n"
                    f"Ran Language Agent Tree Search (LATS) across **{execution_data.get('iteration', 1)} mutation iterations**. "
                    f"Final off-target binding score: **{execution_data.get('off_target_score', 0.15):.3f}** (Safety threshold: `< {execution_data.get('safety_threshold', 0.35):.3f}`).\n\n"
                    f"**Optimized Sequence:** `{execution_data.get('sequence')}`"
                )
            else:
                return f"### 🧪 Vector Redesign Status: {status}\n\nExecution completed with result data: {execution_data}"

        elif agent_id == "memory_rag":
            context_text = retrieved_context[0] if retrieved_context else "Standard BSL operating procedure."
            return (
                f"### 🧠 Grounded Biosafety Intelligence\n\n"
                f"Based on our institutional knowledge base and policy manuals:\n\n"
                f"> *\"{context_text}\"*\n\n"
                f"**Memory Context:** Short-term interaction logged to scratchpad. Rolling buffer actively maintained with automatic episodic overflow routing."
            )

        elif agent_id == "decomposition_planning":
            order = execution_data.get("execution_order", []) if execution_data else []
            return (
                f"### 📐 DAG Task Decomposition & Planning\n\n"
                f"Successfully parsed your objective into a validated **PlanDAG** directed acyclic graph.\n\n"
                f"**Execution Topology:**\n" + "\n".join(f"{i+1}. `{step}`" for i, step in enumerate(order))
            )

        return f"Agent `{agent_id}` executed successfully with status `{status}`."


# Global singleton LLM client
llm_client = LLMClient()

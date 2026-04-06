"""Agent Framework integration — analyst + evaluator agent setup.

Uses the latest Microsoft Foundry SDK (azure-ai-projects >= 2.0.0):
- ``create_version()`` with ``PromptAgentDefinition`` (not the deprecated
  ``create_agent()``).
- ``openai_client.responses.create()`` with ``agent_reference`` (not the
  deprecated threads/runs API).
- ``FunctionTool`` with explicit JSON schemas (not auto-generated from
  type hints).
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, Tool

from domains.analysis.models import AnalysisResult, EvaluationResult, EvaluationVerdict, ToolCallRecord
from shared.credential import create_credential

from .evaluator import EVALUATOR_SYSTEM_PROMPT, build_evaluator_prompt
from .tools import ALL_TOOLS, TOOL_DISPATCH

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

ANALYST_SYSTEM_PROMPT = """
You are the Integrisight.ai integration analyst. You help users understand
their Azure Integration Services landscape by querying the dependency graph.

Rules:
1. ALWAYS use the provided tools to retrieve data. Never fabricate component
   names, IDs, counts, or relationships.
2. If the user asks about something not in the graph data, say so explicitly.
3. When citing components, include their display names and types.
4. For impact analysis, explain what each impacted component does and why
   it would be affected.
5. Be concise but thorough. Use bullet points for lists.
6. If a tool returns an error, report it honestly to the user.
""".strip()


def _get_model_deployment() -> str:
    return os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")


class AgentOrchestrator:
    """Manages analyst and evaluator agents via Microsoft Foundry SDK.

    Agents are created on first use and cleaned up via :meth:`close`.
    """

    def __init__(self) -> None:
        self._project_client: AIProjectClient | None = None
        self._analyst_agent: Any | None = None
        self._evaluator_agent: Any | None = None

    def _get_project_client(self) -> AIProjectClient:
        if self._project_client is None:
            endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
            credential = create_credential()
            self._project_client = AIProjectClient(
                endpoint=endpoint,
                credential=credential,
            )
        return self._project_client

    def _ensure_agents(self) -> None:
        """Create analyst and evaluator agents if not already created."""
        if self._analyst_agent is not None:
            return

        client = self._get_project_client()
        model = _get_model_deployment()

        tools: list[Tool] = list(ALL_TOOLS)

        self._analyst_agent = client.agents.create_version(
            agent_name="integration-analyst",
            definition=PromptAgentDefinition(
                model=model,
                instructions=ANALYST_SYSTEM_PROMPT,
                tools=tools,
                temperature=0.3,
            ),
        )
        logger.info(
            "analyst_agent_created",
            agent_id=self._analyst_agent.id,
            agent_name=self._analyst_agent.name,
        )

        self._evaluator_agent = client.agents.create_version(
            agent_name="quality-evaluator",
            definition=PromptAgentDefinition(
                model=model,
                instructions=EVALUATOR_SYSTEM_PROMPT,
                temperature=0.1,
            ),
        )
        logger.info(
            "evaluator_agent_created",
            agent_id=self._evaluator_agent.id,
            agent_name=self._evaluator_agent.name,
        )

    async def run_analysis(self, user_prompt: str) -> AnalysisResult:
        """Run the full analyst → evaluator flow with up to 1 retry.

        1. Send user prompt to the analyst agent.
        2. Process any function_call tool requests.
        3. Evaluate the analyst response with the evaluator agent.
        4. On FAILED verdict, feed issues back to analyst and retry once.
        """
        self._ensure_agents()
        client = self._get_project_client()
        openai = client.get_openai_client()

        tool_call_records: list[ToolCallRecord] = []
        retry_count = 0

        with openai:
            # --- Step 1: Run analyst ---
            analyst_response, tool_call_records = await self._run_analyst(
                openai, user_prompt, tool_call_records
            )

            # --- Step 2: Evaluate ---
            eval_result = await self._run_evaluator(
                openai, user_prompt, analyst_response, tool_call_records
            )

            # --- Step 3: Retry once on FAILED ---
            if eval_result.verdict == EvaluationVerdict.FAILED and retry_count < 1:
                retry_count += 1
                issues_text = "; ".join(eval_result.issues) if eval_result.issues else eval_result.summary
                revision_prompt = (
                    f"Your previous response had issues: {issues_text}. "
                    f"Please revise your answer using the tools to verify your claims."
                )
                analyst_response, tool_call_records = await self._run_analyst(
                    openai, revision_prompt, tool_call_records
                )
                eval_result = await self._run_evaluator(
                    openai, user_prompt, analyst_response, tool_call_records
                )

        return AnalysisResult(
            response=analyst_response,
            toolCalls=tool_call_records,
            evaluation=eval_result,
            retryCount=retry_count,
        )

    async def _run_analyst(
        self,
        openai: Any,
        prompt: str,
        existing_tool_calls: list[ToolCallRecord],
    ) -> tuple[str, list[ToolCallRecord]]:
        """Send a prompt to the analyst and handle function call loops."""
        from openai.types.responses.response_input_param import FunctionCallOutput

        tool_calls = list(existing_tool_calls)

        # Initial call
        response = openai.responses.create(
            input=prompt,
            extra_body={
                "agent_reference": {
                    "name": self._analyst_agent.name,
                    "type": "agent_reference",
                }
            },
        )

        # Process tool calls in a loop
        max_iterations = 10
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            function_calls = [
                item for item in response.output if item.type == "function_call"
            ]
            if not function_calls:
                break

            # Execute all requested function calls
            outputs = []
            for fc in function_calls:
                tool_name = fc.name
                try:
                    arguments = json.loads(fc.arguments) if fc.arguments else {}
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                executor = TOOL_DISPATCH.get(tool_name)
                if executor is None:
                    output = json.dumps({"error": f"Unknown tool: {tool_name}"})
                else:
                    try:
                        output = await executor(**arguments)
                    except Exception as exc:
                        logger.warning("tool_execution_failed", tool=tool_name, error=str(exc))
                        output = json.dumps({"error": f"Tool execution failed: {exc}"})

                tool_calls.append(ToolCallRecord(
                    toolName=tool_name,
                    arguments=arguments,
                    output=output,
                ))

                outputs.append(
                    FunctionCallOutput(
                        type="function_call_output",
                        call_id=fc.call_id,
                        output=output,
                    )
                )

            # Submit tool outputs and get next response
            response = openai.responses.create(
                input=outputs,
                previous_response_id=response.id,
                extra_body={
                    "agent_reference": {
                        "name": self._analyst_agent.name,
                        "type": "agent_reference",
                    }
                },
            )

        # Extract text response
        analyst_text = response.output_text if hasattr(response, "output_text") else ""
        return analyst_text, tool_calls

    async def _run_evaluator(
        self,
        openai: Any,
        user_prompt: str,
        analyst_response: str,
        tool_calls: list[ToolCallRecord],
    ) -> EvaluationResult:
        """Run the evaluator agent to validate the analyst response."""
        eval_prompt = build_evaluator_prompt(
            user_prompt=user_prompt,
            analyst_response=analyst_response,
            tool_calls=[tc.model_dump(by_alias=True) for tc in tool_calls],
        )

        response = openai.responses.create(
            input=eval_prompt,
            extra_body={
                "agent_reference": {
                    "name": self._evaluator_agent.name,
                    "type": "agent_reference",
                }
            },
        )

        eval_text = response.output_text if hasattr(response, "output_text") else ""

        # Parse structured JSON from evaluator
        try:
            # Strip any markdown code fences
            cleaned = eval_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [line for line in lines if not line.strip().startswith("```")]
                cleaned = "\n".join(lines)
            eval_data = json.loads(cleaned)
            return EvaluationResult(
                verdict=EvaluationVerdict(eval_data.get("verdict", "PASSED")),
                confidence=float(eval_data.get("confidence", 0.5)),
                issues=eval_data.get("issues", []),
                summary=eval_data.get("summary", ""),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning("evaluator_parse_failed", raw=eval_text, error=str(exc))
            return EvaluationResult(
                verdict=EvaluationVerdict.PASSED,
                confidence=0.3,
                issues=[],
                summary="Evaluator response could not be parsed; defaulting to PASSED.",
            )

    async def close(self) -> None:
        """Clean up agent versions and close the project client."""
        if self._project_client is not None:
            try:
                if self._analyst_agent is not None:
                    self._project_client.agents.delete_version(
                        agent_name=self._analyst_agent.name,
                        agent_version=self._analyst_agent.version,
                    )
                if self._evaluator_agent is not None:
                    self._project_client.agents.delete_version(
                        agent_name=self._evaluator_agent.name,
                        agent_version=self._evaluator_agent.version,
                    )
            except Exception:
                logger.warning("agent_cleanup_failed", exc_info=True)
            finally:
                self._project_client.close()
                self._project_client = None
                self._analyst_agent = None
                self._evaluator_agent = None

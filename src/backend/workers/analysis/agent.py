"""Agent Framework integration — analyst + evaluator agent setup.

Uses the Microsoft Agent Framework (``agent-framework`` package) with
``FoundryChatClient`` for Azure AI Foundry integration:

- ``Agent(client=..., tools=[...])`` — agents with typed function tools.
- ``await agent.run(prompt)`` — run the agent and get a response.
- Tools are plain Python async functions; the framework auto-generates
  JSON schemas from type annotations and docstrings.
"""

from __future__ import annotations

import json
import os

import structlog
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

from domains.analysis.models import AnalysisResult, EvaluationResult, EvaluationVerdict, ToolCallRecord
from shared.credential import create_credential

from .evaluator import EVALUATOR_SYSTEM_PROMPT, build_evaluator_prompt
from .tools import ALL_TOOLS

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
    """Manages analyst and evaluator agents via Microsoft Agent Framework.

    Uses ``FoundryChatClient`` + ``Agent`` from the ``agent-framework``
    package. Agents are created on first use and cleaned up via :meth:`close`.
    """

    def __init__(self) -> None:
        self._client: FoundryChatClient | None = None
        self._analyst: Agent | None = None
        self._evaluator: Agent | None = None

    def _get_client(self) -> FoundryChatClient:
        if self._client is None:
            endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
            model = _get_model_deployment()
            credential = create_credential()
            self._client = FoundryChatClient(
                project_endpoint=endpoint,
                model=model,
                credential=credential,
            )
        return self._client

    def _ensure_agents(self) -> None:
        """Create analyst and evaluator agents if not already created."""
        if self._analyst is not None:
            return

        client = self._get_client()

        self._analyst = Agent(
            client=client,
            name="integration-analyst",
            instructions=ANALYST_SYSTEM_PROMPT,
            tools=ALL_TOOLS,
        )
        logger.info("analyst_agent_created", agent_name="integration-analyst")

        self._evaluator = Agent(
            client=client,
            name="quality-evaluator",
            instructions=EVALUATOR_SYSTEM_PROMPT,
        )
        logger.info("evaluator_agent_created", agent_name="quality-evaluator")

    async def run_analysis(self, user_prompt: str) -> AnalysisResult:
        """Run the full analyst → evaluator flow with up to 1 retry.

        1. Send user prompt to the analyst agent.
        2. The framework handles function-call dispatch automatically.
        3. Evaluate the analyst response with the evaluator agent.
        4. On FAILED verdict, feed issues back to analyst and retry once.
        """
        self._ensure_agents()
        assert self._analyst is not None
        assert self._evaluator is not None

        retry_count = 0

        # --- Step 1: Run analyst ---
        analyst_response, tool_call_records = await self._run_analyst(user_prompt)

        # --- Step 2: Evaluate ---
        eval_result = await self._run_evaluator(
            user_prompt, analyst_response, tool_call_records
        )

        # --- Step 3: Retry once on FAILED ---
        if eval_result.verdict == EvaluationVerdict.FAILED and retry_count < 1:
            retry_count += 1
            issues_text = "; ".join(eval_result.issues) if eval_result.issues else eval_result.summary
            revision_prompt = (
                f"Your previous response had issues: {issues_text}. "
                f"Please revise your answer using the tools to verify your claims."
            )
            analyst_response, tool_call_records = await self._run_analyst(revision_prompt)
            eval_result = await self._run_evaluator(
                user_prompt, analyst_response, tool_call_records
            )

        return AnalysisResult(
            response=analyst_response,
            toolCalls=tool_call_records,
            evaluation=eval_result,
            retryCount=retry_count,
        )

    async def _run_analyst(
        self,
        prompt: str,
    ) -> tuple[str, list[ToolCallRecord]]:
        """Send a prompt to the analyst agent.

        The Agent Framework handles function-call dispatch automatically —
        it invokes the tool functions and feeds results back to the model.
        """
        assert self._analyst is not None

        response = await self._analyst.run(prompt)

        # Extract tool call records from the response messages
        tool_call_records: list[ToolCallRecord] = []
        for message in response.messages:
            for content in message.contents:
                if content.type == "function_call":
                    tool_call_records.append(ToolCallRecord(
                        toolName=getattr(content, "name", "unknown"),
                        arguments=getattr(content, "arguments", {}),
                        output=None,
                    ))
                elif content.type == "function_result":
                    result_str = getattr(content, "result", "")
                    if tool_call_records:
                        tool_call_records[-1].output = result_str

        analyst_text = response.text or ""
        return analyst_text, tool_call_records

    async def _run_evaluator(
        self,
        user_prompt: str,
        analyst_response: str,
        tool_calls: list[ToolCallRecord],
    ) -> EvaluationResult:
        """Run the evaluator agent to validate the analyst response."""
        assert self._evaluator is not None

        eval_prompt = build_evaluator_prompt(
            user_prompt=user_prompt,
            analyst_response=analyst_response,
            tool_calls=[tc.model_dump(by_alias=True) for tc in tool_calls],
        )

        response = await self._evaluator.run(eval_prompt)
        eval_text = response.text or ""

        # Parse structured JSON from evaluator
        return self._parse_evaluation(eval_text)

    @staticmethod
    def _parse_evaluation(eval_text: str) -> EvaluationResult:
        """Parse the evaluator's JSON response into an EvaluationResult."""
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
        """Clean up agents and close the client."""
        try:
            if self._analyst is not None:
                if hasattr(self._analyst, "close"):
                    await self._analyst.close()
                elif hasattr(self._analyst, "__aexit__"):
                    await self._analyst.__aexit__(None, None, None)
            if self._evaluator is not None:
                if hasattr(self._evaluator, "close"):
                    await self._evaluator.close()
                elif hasattr(self._evaluator, "__aexit__"):
                    await self._evaluator.__aexit__(None, None, None)
        except Exception:
            logger.warning("agent_cleanup_failed", exc_info=True)
        finally:
            self._client = None
            self._analyst = None
            self._evaluator = None

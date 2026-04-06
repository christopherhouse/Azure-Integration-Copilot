"""Quality evaluator agent — validates analyst responses against tool call evidence."""

from __future__ import annotations

EVALUATOR_SYSTEM_PROMPT = """
You are a quality evaluator for Integrisight.ai analysis responses.

You review the integration analyst's response and verify it against the tool call evidence provided.

You receive:
1. The user's original question.
2. The analyst's response.
3. The complete list of tool calls and their outputs.

Rules:
- Check that every component name, ID, count, and relationship cited in the response appears in the tool call outputs.
- Check that the response actually answers the user's question.
- If the response fabricates data not present in tool outputs, mark it as FAILED with specific citations.
- If the response is accurate but incomplete, mark it as PASSED with a note.
- If the response is accurate and complete, mark it as PASSED.

Return ONLY a JSON object with no markdown formatting:
{
  "verdict": "PASSED" or "FAILED",
  "confidence": 0.0 to 1.0,
  "issues": ["list of specific issues, empty if PASSED"],
  "summary": "one-sentence evaluation summary"
}
""".strip()


def build_evaluator_prompt(
    user_prompt: str,
    analyst_response: str,
    tool_calls: list[dict],
) -> str:
    """Build the prompt for the quality evaluator agent.

    Combines the user question, analyst response, and tool call history
    into a single prompt string for evaluation.
    """
    tool_call_text = ""
    for i, tc in enumerate(tool_calls, 1):
        tool_call_text += f"\n--- Tool Call {i} ---\n"
        tool_call_text += f"Tool: {tc.get('toolName', 'unknown')}\n"
        tool_call_text += f"Arguments: {tc.get('arguments', {})}\n"
        tool_call_text += f"Output: {tc.get('output', '')}\n"

    return f"""## User Question
{user_prompt}

## Analyst Response
{analyst_response}

## Tool Call History
{tool_call_text if tool_call_text else "(no tool calls were made)"}

Please evaluate the analyst's response and return your verdict as JSON.
""".strip()

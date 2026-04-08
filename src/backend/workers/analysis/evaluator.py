"""Quality evaluator agent — validates analyst responses against tool call evidence."""

from __future__ import annotations

from prompts import EVALUATOR_USER_TEMPLATE


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

    return EVALUATOR_USER_TEMPLATE.format(
        user_prompt=user_prompt,
        analyst_response=analyst_response,
        tool_call_history=tool_call_text if tool_call_text else "(no tool calls were made)",
    )

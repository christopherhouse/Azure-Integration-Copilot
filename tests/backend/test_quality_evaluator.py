"""Tests for the quality evaluator prompt builder."""

import os
from unittest.mock import patch

import pytest

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "WEB_PUBSUB_ENDPOINT": "https://fake-pubsub.webpubsub.azure.com",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from workers.analysis.evaluator import EVALUATOR_SYSTEM_PROMPT, build_evaluator_prompt


class TestBuildEvaluatorPrompt:
    """Tests for build_evaluator_prompt."""

    def test_includes_user_question(self):
        prompt = build_evaluator_prompt(
            user_prompt="What are the main patterns?",
            analyst_response="There are several patterns...",
            tool_calls=[],
        )
        assert "What are the main patterns?" in prompt
        assert "## User Question" in prompt

    def test_includes_analyst_response(self):
        prompt = build_evaluator_prompt(
            user_prompt="Test question",
            analyst_response="The integration landscape shows...",
            tool_calls=[],
        )
        assert "The integration landscape shows..." in prompt
        assert "## Analyst Response" in prompt

    def test_includes_tool_calls(self):
        tool_calls = [
            {
                "toolName": "get_project_summary",
                "arguments": {},
                "output": '{"totalComponents": 10}',
            },
            {
                "toolName": "get_component_details",
                "arguments": {"component_id": "cmp_001"},
                "output": '{"id": "cmp_001"}',
            },
        ]
        prompt = build_evaluator_prompt(
            user_prompt="Test",
            analyst_response="Response",
            tool_calls=tool_calls,
        )
        assert "get_project_summary" in prompt
        assert "get_component_details" in prompt
        assert "cmp_001" in prompt
        assert "Tool Call 1" in prompt
        assert "Tool Call 2" in prompt

    def test_handles_empty_tool_calls(self):
        prompt = build_evaluator_prompt(
            user_prompt="Test",
            analyst_response="Response",
            tool_calls=[],
        )
        assert "(no tool calls were made)" in prompt

    def test_includes_tool_call_history_header(self):
        prompt = build_evaluator_prompt(
            user_prompt="Test",
            analyst_response="Response",
            tool_calls=[],
        )
        assert "## Tool Call History" in prompt

    def test_prompt_ends_with_evaluation_instruction(self):
        prompt = build_evaluator_prompt(
            user_prompt="Test",
            analyst_response="Response",
            tool_calls=[],
        )
        assert "evaluate" in prompt.lower()
        assert "verdict" in prompt.lower()


class TestEvaluatorSystemPrompt:
    """Tests for the evaluator system prompt constant."""

    def test_is_non_empty_string(self):
        assert isinstance(EVALUATOR_SYSTEM_PROMPT, str)
        assert len(EVALUATOR_SYSTEM_PROMPT) > 100

    def test_mentions_verdict_options(self):
        assert "PASSED" in EVALUATOR_SYSTEM_PROMPT
        assert "FAILED" in EVALUATOR_SYSTEM_PROMPT

    def test_mentions_json_format(self):
        assert "JSON" in EVALUATOR_SYSTEM_PROMPT

    def test_includes_evaluation_criteria(self):
        assert "tool" in EVALUATOR_SYSTEM_PROMPT.lower()
        assert "confidence" in EVALUATOR_SYSTEM_PROMPT.lower()
        assert "issues" in EVALUATOR_SYSTEM_PROMPT.lower()

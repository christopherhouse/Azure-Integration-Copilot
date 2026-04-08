"""Tests for the prompt loader module (src/backend/prompts/__init__.py).

Verifies that all prompt constants are loaded correctly from their text files,
contain expected key phrases, and that templates can be formatted with the
documented placeholders.
"""

from __future__ import annotations

import os
from unittest.mock import patch

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "WEB_PUBSUB_ENDPOINT": "https://fake-pubsub.webpubsub.azure.com",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from prompts import (
        ANALYST_REVISION_TEMPLATE,
        ANALYST_SYSTEM_PROMPT,
        EVALUATOR_SYSTEM_PROMPT,
        EVALUATOR_USER_TEMPLATE,
    )


# ── Helpers ────────────────────────────────────────────────────────────


_ALL_CONSTANTS: dict[str, str] = {
    "ANALYST_SYSTEM_PROMPT": ANALYST_SYSTEM_PROMPT,
    "EVALUATOR_SYSTEM_PROMPT": EVALUATOR_SYSTEM_PROMPT,
    "EVALUATOR_USER_TEMPLATE": EVALUATOR_USER_TEMPLATE,
    "ANALYST_REVISION_TEMPLATE": ANALYST_REVISION_TEMPLATE,
}


# ── Tests: basic loading ──────────────────────────────────────────────


class TestPromptConstantsAreLoaded:
    """All public constants must be non-empty strings after import."""

    def test_analyst_system_prompt_is_nonempty_string(self) -> None:
        assert isinstance(ANALYST_SYSTEM_PROMPT, str)
        assert len(ANALYST_SYSTEM_PROMPT) > 0

    def test_evaluator_system_prompt_is_nonempty_string(self) -> None:
        assert isinstance(EVALUATOR_SYSTEM_PROMPT, str)
        assert len(EVALUATOR_SYSTEM_PROMPT) > 0

    def test_evaluator_user_template_is_nonempty_string(self) -> None:
        assert isinstance(EVALUATOR_USER_TEMPLATE, str)
        assert len(EVALUATOR_USER_TEMPLATE) > 0

    def test_analyst_revision_template_is_nonempty_string(self) -> None:
        assert isinstance(ANALYST_REVISION_TEMPLATE, str)
        assert len(ANALYST_REVISION_TEMPLATE) > 0

    def test_no_constant_has_leading_or_trailing_whitespace(self) -> None:
        for name, value in _ALL_CONSTANTS.items():
            assert value == value.strip(), (
                f"{name} has leading/trailing whitespace"
            )


# ── Tests: static prompt content ──────────────────────────────────────


class TestAnalystSystemPrompt:
    """The analyst system prompt must contain key domain phrases."""

    def test_mentions_integrisight_analyst_role(self) -> None:
        assert "Integrisight.ai integration analyst" in ANALYST_SYSTEM_PROMPT

    def test_mentions_tools_usage_rule(self) -> None:
        assert "tools" in ANALYST_SYSTEM_PROMPT.lower()

    def test_mentions_never_fabricate(self) -> None:
        assert "Never fabricate" in ANALYST_SYSTEM_PROMPT


class TestEvaluatorSystemPrompt:
    """The evaluator system prompt must describe the verdict schema."""

    def test_mentions_passed_verdict(self) -> None:
        assert "PASSED" in EVALUATOR_SYSTEM_PROMPT

    def test_mentions_failed_verdict(self) -> None:
        assert "FAILED" in EVALUATOR_SYSTEM_PROMPT

    def test_mentions_json_output(self) -> None:
        assert "JSON" in EVALUATOR_SYSTEM_PROMPT

    def test_mentions_confidence_field(self) -> None:
        assert "confidence" in EVALUATOR_SYSTEM_PROMPT

    def test_mentions_issues_field(self) -> None:
        assert "issues" in EVALUATOR_SYSTEM_PROMPT


# ── Tests: template formatting ────────────────────────────────────────


class TestEvaluatorUserTemplate:
    """The evaluator user template must accept documented placeholders."""

    def test_contains_user_prompt_placeholder(self) -> None:
        assert "{user_prompt}" in EVALUATOR_USER_TEMPLATE

    def test_contains_analyst_response_placeholder(self) -> None:
        assert "{analyst_response}" in EVALUATOR_USER_TEMPLATE

    def test_contains_tool_call_history_placeholder(self) -> None:
        assert "{tool_call_history}" in EVALUATOR_USER_TEMPLATE

    def test_format_with_all_placeholders(self) -> None:
        result = EVALUATOR_USER_TEMPLATE.format(
            user_prompt="What APIs depend on X?",
            analyst_response="API-A and API-B depend on X.",
            tool_call_history="get_graph_neighbors -> [A, B]",
        )
        assert "{user_prompt}" not in result
        assert "{analyst_response}" not in result
        assert "{tool_call_history}" not in result

    def test_format_produces_expected_content(self) -> None:
        result = EVALUATOR_USER_TEMPLATE.format(
            user_prompt="question-alpha",
            analyst_response="answer-beta",
            tool_call_history="history-gamma",
        )
        assert "question-alpha" in result
        assert "answer-beta" in result
        assert "history-gamma" in result

    def test_format_missing_placeholder_raises(self) -> None:
        """Omitting a required placeholder must raise KeyError."""
        import pytest

        with pytest.raises(KeyError):
            EVALUATOR_USER_TEMPLATE.format(user_prompt="only one")


class TestAnalystRevisionTemplate:
    """The analyst revision template must accept the issues_text placeholder."""

    def test_contains_issues_text_placeholder(self) -> None:
        assert "{issues_text}" in ANALYST_REVISION_TEMPLATE

    def test_format_with_issues_text(self) -> None:
        result = ANALYST_REVISION_TEMPLATE.format(
            issues_text="Claim X is unsupported by tool output",
        )
        assert "{issues_text}" not in result
        assert "Claim X is unsupported by tool output" in result

    def test_format_missing_issues_text_raises(self) -> None:
        """Omitting the issues_text placeholder must raise KeyError."""
        import pytest

        with pytest.raises(KeyError):
            ANALYST_REVISION_TEMPLATE.format(unrelated="value")

    def test_mentions_revise_instruction(self) -> None:
        assert "revise" in ANALYST_REVISION_TEMPLATE.lower()

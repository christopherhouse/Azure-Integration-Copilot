"""Tests for the artifact status state machine — valid and invalid transitions."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from domains.artifacts.models import (
    ArtifactStatus,
    InvalidStatusTransition,
    VALID_TRANSITIONS,
    transition_status,
)


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    """Test all valid status transitions succeed."""

    def test_uploading_to_uploaded(self):
        result = transition_status(ArtifactStatus.UPLOADING, ArtifactStatus.UPLOADED)
        assert result == ArtifactStatus.UPLOADED

    def test_uploading_to_unsupported(self):
        result = transition_status(ArtifactStatus.UPLOADING, ArtifactStatus.UNSUPPORTED)
        assert result == ArtifactStatus.UNSUPPORTED

    def test_uploaded_to_scanning(self):
        result = transition_status(ArtifactStatus.UPLOADED, ArtifactStatus.SCANNING)
        assert result == ArtifactStatus.SCANNING

    def test_scanning_to_scan_passed(self):
        result = transition_status(ArtifactStatus.SCANNING, ArtifactStatus.SCAN_PASSED)
        assert result == ArtifactStatus.SCAN_PASSED

    def test_scanning_to_scan_failed(self):
        result = transition_status(ArtifactStatus.SCANNING, ArtifactStatus.SCAN_FAILED)
        assert result == ArtifactStatus.SCAN_FAILED

    def test_scan_passed_to_parsing(self):
        result = transition_status(ArtifactStatus.SCAN_PASSED, ArtifactStatus.PARSING)
        assert result == ArtifactStatus.PARSING

    def test_parsing_to_parsed(self):
        result = transition_status(ArtifactStatus.PARSING, ArtifactStatus.PARSED)
        assert result == ArtifactStatus.PARSED

    def test_parsing_to_parse_failed(self):
        result = transition_status(ArtifactStatus.PARSING, ArtifactStatus.PARSE_FAILED)
        assert result == ArtifactStatus.PARSE_FAILED

    def test_parsed_to_graph_building(self):
        result = transition_status(ArtifactStatus.PARSED, ArtifactStatus.GRAPH_BUILDING)
        assert result == ArtifactStatus.GRAPH_BUILDING

    def test_graph_building_to_graph_built(self):
        result = transition_status(ArtifactStatus.GRAPH_BUILDING, ArtifactStatus.GRAPH_BUILT)
        assert result == ArtifactStatus.GRAPH_BUILT

    def test_graph_building_to_graph_failed(self):
        result = transition_status(ArtifactStatus.GRAPH_BUILDING, ArtifactStatus.GRAPH_FAILED)
        assert result == ArtifactStatus.GRAPH_FAILED

    def test_scanning_to_scanning_idempotent(self):
        """Self-transition allows idempotent retries during scanning."""
        result = transition_status(ArtifactStatus.SCANNING, ArtifactStatus.SCANNING)
        assert result == ArtifactStatus.SCANNING

    def test_parsing_to_parsing_idempotent(self):
        """Self-transition allows idempotent retries during parsing."""
        result = transition_status(ArtifactStatus.PARSING, ArtifactStatus.PARSING)
        assert result == ArtifactStatus.PARSING

    def test_graph_building_to_graph_building_idempotent(self):
        """Self-transition allows idempotent retries during graph building."""
        result = transition_status(ArtifactStatus.GRAPH_BUILDING, ArtifactStatus.GRAPH_BUILDING)
        assert result == ArtifactStatus.GRAPH_BUILDING


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    """Test that invalid transitions raise InvalidStatusTransition."""

    def test_uploading_to_scanning_raises(self):
        with pytest.raises(InvalidStatusTransition) as exc_info:
            transition_status(ArtifactStatus.UPLOADING, ArtifactStatus.SCANNING)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "INVALID_STATUS_TRANSITION"

    def test_uploaded_to_parsed_raises(self):
        with pytest.raises(InvalidStatusTransition):
            transition_status(ArtifactStatus.UPLOADED, ArtifactStatus.PARSED)

    def test_scanning_to_uploaded_raises(self):
        with pytest.raises(InvalidStatusTransition):
            transition_status(ArtifactStatus.SCANNING, ArtifactStatus.UPLOADED)

    def test_scan_failed_is_terminal(self):
        """scan_failed has no valid outgoing transitions."""
        with pytest.raises(InvalidStatusTransition):
            transition_status(ArtifactStatus.SCAN_FAILED, ArtifactStatus.PARSING)

    def test_parse_failed_is_terminal(self):
        with pytest.raises(InvalidStatusTransition):
            transition_status(ArtifactStatus.PARSE_FAILED, ArtifactStatus.GRAPH_BUILDING)

    def test_graph_failed_is_terminal(self):
        with pytest.raises(InvalidStatusTransition):
            transition_status(ArtifactStatus.GRAPH_FAILED, ArtifactStatus.GRAPH_BUILT)

    def test_graph_built_is_terminal(self):
        with pytest.raises(InvalidStatusTransition):
            transition_status(ArtifactStatus.GRAPH_BUILT, ArtifactStatus.UPLOADING)

    def test_unsupported_is_terminal(self):
        with pytest.raises(InvalidStatusTransition):
            transition_status(ArtifactStatus.UNSUPPORTED, ArtifactStatus.SCANNING)

    def test_backward_transition_raises(self):
        """Cannot go backwards in the pipeline."""
        with pytest.raises(InvalidStatusTransition):
            transition_status(ArtifactStatus.PARSED, ArtifactStatus.SCANNING)


# ---------------------------------------------------------------------------
# Status enum completeness
# ---------------------------------------------------------------------------


class TestArtifactStatusEnum:
    """Test ArtifactStatus enum has all expected values."""

    def test_all_12_statuses_defined(self):
        assert len(ArtifactStatus) == 12

    def test_expected_status_values(self):
        expected = {
            "uploading", "uploaded", "scanning", "scan_passed", "scan_failed",
            "parsing", "parsed", "parse_failed", "graph_building", "graph_built",
            "graph_failed", "unsupported",
        }
        actual = {s.value for s in ArtifactStatus}
        assert actual == expected

    def test_valid_transitions_cover_non_terminal_statuses(self):
        """Every non-terminal status should have at least one outgoing transition."""
        terminal_statuses = {
            ArtifactStatus.SCAN_FAILED,
            ArtifactStatus.PARSE_FAILED,
            ArtifactStatus.GRAPH_FAILED,
            ArtifactStatus.GRAPH_BUILT,
            ArtifactStatus.UNSUPPORTED,
        }
        non_terminal = set(ArtifactStatus) - terminal_statuses
        for status in non_terminal:
            assert status in VALID_TRANSITIONS, f"{status} should have valid transitions"
            assert len(VALID_TRANSITIONS[status]) > 0, f"{status} should have at least one target"


# ---------------------------------------------------------------------------
# InvalidStatusTransition exception
# ---------------------------------------------------------------------------


class TestInvalidStatusTransitionException:
    """Test InvalidStatusTransition exception properties."""

    def test_exception_attributes(self):
        exc = InvalidStatusTransition(current="uploading", target="parsed")
        assert exc.status_code == 409
        assert exc.code == "INVALID_STATUS_TRANSITION"
        assert "uploading" in exc.message
        assert "parsed" in exc.message
        assert exc.detail == {"current": "uploading", "target": "parsed"}

    def test_exception_is_app_error(self):
        from shared.exceptions import AppError
        exc = InvalidStatusTransition(current="uploading", target="parsed")
        assert isinstance(exc, AppError)

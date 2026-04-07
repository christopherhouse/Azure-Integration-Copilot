"""Tests for the analysis worker handler (AnalysisHandler)."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "WEB_PUBSUB_ENDPOINT": "https://fake-pubsub.webpubsub.azure.com",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from domains.analysis.models import (
        Analysis,
        AnalysisResult,
        AnalysisStatus,
        EvaluationResult,
        EvaluationVerdict,
    )
    from workers.analysis.handler import AnalysisHandler
    from workers.analysis.tools.scoping import AnalysisContext, analysis_context
    from workers.base import PermanentError, TransientError


def _make_analysis(
    analysis_id: str = "ana_test123",
    tenant_id: str = "t1",
    project_id: str = "p1",
    status: AnalysisStatus = AnalysisStatus.PENDING,
) -> Analysis:
    now = datetime.now(UTC)
    return Analysis(
        id=analysis_id,
        partitionKey=f"{tenant_id}:{project_id}",
        tenantId=tenant_id,
        projectId=project_id,
        prompt="Analyze my integrations",
        status=status,
        requestedBy="u1",
        createdAt=now,
    )


def _make_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        response="Here is the analysis...",
        toolCalls=[],
        evaluation=EvaluationResult(
            verdict=EvaluationVerdict.PASSED,
            confidence=0.9,
            issues=[],
            summary="Good response.",
        ),
        retryCount=0,
    )


def _make_event_data(
    tenant_id: str = "t1",
    project_id: str = "p1",
    analysis_id: str = "ana_test123",
    prompt: str = "Analyze my integrations",
) -> dict:
    return {
        "tenantId": tenant_id,
        "projectId": project_id,
        "analysisId": analysis_id,
        "prompt": prompt,
    }


def _make_handler(
    analysis_repo=None,
    publisher=None,
    pubsub=None,
    orchestrator=None,
    analysis=None,
    result=None,
):
    if analysis_repo is None:
        analysis_repo = AsyncMock()
        analysis_repo.get_by_id = AsyncMock(
            return_value=analysis or _make_analysis()
        )
        analysis_repo.update = AsyncMock()

    if publisher is None:
        publisher = AsyncMock()

    if pubsub is None:
        pubsub = AsyncMock()

    if orchestrator is None:
        orchestrator = AsyncMock()
        orchestrator.run_analysis = AsyncMock(
            return_value=result or _make_analysis_result()
        )

    handler = AnalysisHandler(
        analysis_repository=analysis_repo,
        event_publisher=publisher,
        pubsub_service=pubsub,
        agent_orchestrator=orchestrator,
    )
    return handler, analysis_repo, publisher, pubsub, orchestrator


class TestAnalysisHandlerIsAlreadyProcessed:
    """Tests for the idempotency check."""

    @pytest.mark.asyncio
    async def test_returns_false_when_analysis_not_found(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(return_value=None)
        result = await handler.is_already_processed(_make_event_data())
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_status_is_pending(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(
            return_value=_make_analysis(status=AnalysisStatus.PENDING)
        )
        result = await handler.is_already_processed(_make_event_data())
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_status_is_running(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(
            return_value=_make_analysis(status=AnalysisStatus.RUNNING)
        )
        result = await handler.is_already_processed(_make_event_data())
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_status_is_completed(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(
            return_value=_make_analysis(status=AnalysisStatus.COMPLETED)
        )
        result = await handler.is_already_processed(_make_event_data())
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_status_is_failed(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(
            return_value=_make_analysis(status=AnalysisStatus.FAILED)
        )
        result = await handler.is_already_processed(_make_event_data())
        assert result is True


class TestAnalysisHandlerHandle:
    """Tests for the analysis handler ``handle`` method."""

    @pytest.mark.asyncio
    async def test_transitions_through_pending_to_running_to_completed(self):
        captured_statuses = []

        async def _capture_update(analysis):
            captured_statuses.append(analysis.status)

        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=_make_analysis())
        repo.update = AsyncMock(side_effect=_capture_update)

        handler, _, publisher, _, orchestrator = _make_handler(analysis_repo=repo)
        await handler.handle(_make_event_data())

        # Should update twice: once for running, once for completed
        assert len(captured_statuses) == 2
        assert captured_statuses[0] == AnalysisStatus.RUNNING
        assert captured_statuses[1] == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_calls_agent_orchestrator(self):
        handler, _, _, _, orchestrator = _make_handler()
        await handler.handle(_make_event_data())

        orchestrator.run_analysis.assert_awaited_once_with("Analyze my integrations")

    @pytest.mark.asyncio
    async def test_publishes_analysis_completed_event(self):
        handler, _, publisher, *_ = _make_handler()
        await handler.handle(_make_event_data())

        publisher.publish_event.assert_awaited_once()
        event = publisher.publish_event.call_args.args[0]
        assert event.type == "com.integration-copilot.analysis.completed.v1"
        assert event.data["tenantId"] == "t1"
        assert event.data["projectId"] == "p1"
        assert event.data["analysisId"] == "ana_test123"

    @pytest.mark.asyncio
    async def test_raises_permanent_error_when_analysis_not_found(self):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=None)
        repo.update = AsyncMock()
        handler, *_ = _make_handler(analysis_repo=repo)

        with pytest.raises(PermanentError, match="not found"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_orchestrator_failure(self):
        orchestrator = AsyncMock()
        orchestrator.run_analysis = AsyncMock(
            side_effect=RuntimeError("AI service down")
        )
        handler, *_ = _make_handler(orchestrator=orchestrator)

        with pytest.raises(TransientError, match="Analysis failed"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_sets_analysis_context_before_orchestrator(self):
        """Verify that the scoping context is set correctly for tool invocations."""
        captured_context = {}

        async def _capture_context(prompt):
            ctx = analysis_context.get()
            captured_context["tenant_id"] = ctx.tenant_id
            captured_context["project_id"] = ctx.project_id
            return _make_analysis_result()

        orchestrator = AsyncMock()
        orchestrator.run_analysis = _capture_context
        handler, *_ = _make_handler(orchestrator=orchestrator)

        await handler.handle(_make_event_data())

        assert captured_context["tenant_id"] == "t1"
        assert captured_context["project_id"] == "p1"

    @pytest.mark.asyncio
    async def test_resets_context_after_success(self):
        handler, *_ = _make_handler()
        await handler.handle(_make_event_data())

        # Context should be reset (accessing it should raise LookupError)
        with pytest.raises(LookupError):
            analysis_context.get()

    @pytest.mark.asyncio
    async def test_resets_context_after_failure(self):
        orchestrator = AsyncMock()
        orchestrator.run_analysis = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        handler, *_ = _make_handler(orchestrator=orchestrator)

        with pytest.raises(TransientError):
            await handler.handle(_make_event_data())

        # Context should be reset even after failure
        with pytest.raises(LookupError):
            analysis_context.get()

    @pytest.mark.asyncio
    async def test_includes_verdict_in_published_event(self):
        result = _make_analysis_result()
        handler, _, publisher, *_ = _make_handler(result=result)
        await handler.handle(_make_event_data())

        event = publisher.publish_event.call_args.args[0]
        assert event.data["verdict"] == "PASSED"


class TestAnalysisHandlerHandleFailure:
    """Tests for the analysis handler failure handler."""

    @pytest.mark.asyncio
    async def test_transitions_to_failed(self):
        handler, repo, publisher, *_ = _make_handler()
        await handler.handle_failure(
            _make_event_data(), PermanentError("bad data")
        )

        repo.update.assert_awaited_once()
        updated_analysis = repo.update.call_args.args[0]
        assert updated_analysis.status == AnalysisStatus.FAILED
        assert "bad data" in updated_analysis.error
        assert updated_analysis.completed_at is not None

    @pytest.mark.asyncio
    async def test_publishes_analysis_failed_event(self):
        handler, _, publisher, *_ = _make_handler()
        await handler.handle_failure(
            _make_event_data(), PermanentError("bad data")
        )

        publisher.publish_event.assert_awaited_once()
        event = publisher.publish_event.call_args.args[0]
        assert event.type == "com.integration-copilot.analysis.failed.v1"
        assert event.data["error"] == "bad data"

    @pytest.mark.asyncio
    async def test_does_not_crash_when_analysis_not_found(self):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=None)
        handler, *_ = _make_handler(analysis_repo=repo)

        # Should not raise
        await handler.handle_failure(
            _make_event_data(), PermanentError("bad data")
        )

    @pytest.mark.asyncio
    async def test_does_not_raise_on_internal_error(self):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(side_effect=RuntimeError("db down"))
        handler, *_ = _make_handler(analysis_repo=repo)

        # Should not raise
        await handler.handle_failure(
            _make_event_data(), PermanentError("bad data")
        )

"""Tests for the parser worker handler (end-to-end with mocks)."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from domains.artifacts.models import Artifact, ArtifactStatus
    from workers.base import PermanentError, TransientError
    from workers.parser.handler import ParserHandler


def _make_artifact(
    artifact_id: str = "art_test123",
    tenant_id: str = "t1",
    project_id: str = "p1",
    status: ArtifactStatus = ArtifactStatus.SCAN_PASSED,
    artifact_type: str = "logic_app_workflow",
    blob_path: str | None = "tenants/t1/projects/p1/artifacts/art_test123/test-workflow.json",
) -> Artifact:
    now = datetime.now(UTC)
    return Artifact(
        id=artifact_id,
        partitionKey=tenant_id,
        tenantId=tenant_id,
        projectId=project_id,
        name="test-workflow.json",
        artifactType=artifact_type,
        status=status,
        fileSizeBytes=1024,
        blobPath=blob_path,
        createdAt=now,
        updatedAt=now,
    )


def _make_event_data(
    tenant_id: str = "t1",
    project_id: str = "p1",
    artifact_id: str = "art_test123",
) -> dict:
    """Build a minimal event payload matching what the scan-gate worker publishes."""
    return {
        "tenantId": tenant_id,
        "projectId": project_id,
        "artifactId": artifact_id,
    }


_SAMPLE_LOGIC_APP = b"""{
    "definition": {
        "triggers": {"manual": {"type": "Request"}},
        "actions": {"action1": {"type": "Http", "inputs": {"method": "GET", "uri": "https://api.example.com/data"}}}
    }
}"""


def _make_handler(
    repo=None,
    blob=None,
    cosmos=None,
    publisher=None,
    blob_content: bytes = _SAMPLE_LOGIC_APP,
    artifact_type: str = "logic_app_workflow",
):
    if repo is None:
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=_make_artifact(artifact_type=artifact_type))
        repo.update_status = AsyncMock(
            side_effect=[
                _make_artifact(status=ArtifactStatus.PARSING, artifact_type=artifact_type),
                _make_artifact(status=ArtifactStatus.PARSED, artifact_type=artifact_type),
            ]
        )
        repo.update = AsyncMock()
    if blob is None:
        blob = AsyncMock()
        blob.download_blob = AsyncMock(return_value=blob_content)
    if cosmos is None:
        cosmos = AsyncMock()
        mock_container = AsyncMock()
        mock_container.create_item = AsyncMock(return_value={})
        cosmos.get_container = AsyncMock(return_value=mock_container)
    if publisher is None:
        publisher = AsyncMock()

    return ParserHandler(
        artifact_repository=repo,
        blob_service=blob,
        cosmos_service=cosmos,
        event_publisher=publisher,
    ), repo, blob, cosmos, publisher


class TestParserIsAlreadyProcessed:
    """Tests for the idempotency check."""

    @pytest.mark.asyncio
    async def test_returns_false_when_artifact_not_found(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(return_value=None)
        result = await handler.is_already_processed(_make_event_data())
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_status_is_scan_passed(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(return_value=_make_artifact(status=ArtifactStatus.SCAN_PASSED))
        result = await handler.is_already_processed(_make_event_data())
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_status_is_parsing(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(return_value=_make_artifact(status=ArtifactStatus.PARSING))
        result = await handler.is_already_processed(_make_event_data())
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_status_is_parsed(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(return_value=_make_artifact(status=ArtifactStatus.PARSED))
        result = await handler.is_already_processed(_make_event_data())
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_status_is_graph_built(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(return_value=_make_artifact(status=ArtifactStatus.GRAPH_BUILT))
        result = await handler.is_already_processed(_make_event_data())
        assert result is True


class TestParserHandle:
    """Tests for the parser handler ``handle`` method."""

    @pytest.mark.asyncio
    async def test_full_pipeline_logic_app(self):
        handler, repo, blob, cosmos, publisher = _make_handler()
        await handler.handle(_make_event_data())

        # Two status transitions: scan_passed→parsing, parsing→parsed
        assert repo.update_status.await_count == 2
        calls = repo.update_status.await_args_list
        assert calls[0].args == ("t1", "art_test123", ArtifactStatus.PARSING)
        assert calls[1].args == ("t1", "art_test123", ArtifactStatus.PARSED)

        # Blob downloaded
        blob.download_blob.assert_awaited_once()

        # Parse result stored in Cosmos
        mock_container = await cosmos.get_container()
        mock_container.create_item.assert_awaited_once()
        stored_doc = mock_container.create_item.call_args.kwargs["body"]
        assert stored_doc["type"] == "parse_result"
        assert stored_doc["artifactId"] == "art_test123"
        assert len(stored_doc["components"]) > 0

        # Event published
        publisher.publish_event.assert_awaited_once()
        published_event = publisher.publish_event.call_args.args[0]
        assert published_event.type == "com.integration-copilot.artifact.parsed.v1"
        assert published_event.data["componentCount"] > 0

    @pytest.mark.asyncio
    async def test_full_pipeline_openapi(self):
        openapi_content = b'{"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0"}, "paths": {"/test": {"get": {"summary": "Test"}}}}'
        handler, repo, blob, cosmos, publisher = _make_handler(
            blob_content=openapi_content, artifact_type="openapi_spec"
        )

        await handler.handle(_make_event_data())

        publisher.publish_event.assert_awaited_once()
        published_event = publisher.publish_event.call_args.args[0]
        assert published_event.data["componentCount"] == 2  # api_definition + 1 operation

    @pytest.mark.asyncio
    async def test_full_pipeline_apim_policy(self):
        apim_content = b"<policies><inbound><base /></inbound></policies>"
        handler, repo, blob, cosmos, publisher = _make_handler(
            blob_content=apim_content, artifact_type="apim_policy"
        )

        await handler.handle(_make_event_data())

        publisher.publish_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_permanent_error_when_artifact_not_found(self):
        handler, repo, *_ = _make_handler()
        repo.update_status = AsyncMock(return_value=None)

        with pytest.raises(PermanentError, match="not found"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_status_transition_failure(self):
        handler, repo, *_ = _make_handler()
        repo.update_status = AsyncMock(side_effect=RuntimeError("cosmos timeout"))

        with pytest.raises(TransientError, match="parsing"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_blob_download_failure(self):
        handler, repo, blob, *_ = _make_handler()
        blob.download_blob = AsyncMock(side_effect=RuntimeError("blob error"))

        with pytest.raises(TransientError, match="download blob"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_permanent_error_on_unsupported_type(self):
        handler, repo, blob, *_ = _make_handler(artifact_type="unknown_type")
        blob.download_blob = AsyncMock(return_value=b"content")

        with pytest.raises(PermanentError, match="No parser registered"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_permanent_error_on_parse_error(self):
        handler, repo, blob, *_ = _make_handler(blob_content=b"not valid json!")

        with pytest.raises(PermanentError, match="Parse error"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_cosmos_store_failure(self):
        handler, repo, blob, cosmos, publisher = _make_handler()
        mock_container = AsyncMock()
        mock_container.create_item = AsyncMock(side_effect=RuntimeError("cosmos write failed"))
        cosmos.get_container = AsyncMock(return_value=mock_container)

        with pytest.raises(TransientError, match="store parse result"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_retries_when_already_in_parsing_status(self):
        """On retry after a transient failure, the artifact is already in PARSING.
        The handler should skip the status transition and proceed with parsing."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.PARSING)
        )
        # Only one update_status call expected (parsing → parsed)
        repo.update_status = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.PARSED)
        )
        handler, _, blob, cosmos, publisher = _make_handler(repo=repo)

        await handler.handle(_make_event_data())

        # Should NOT have tried scan_passed→parsing; only parsing→parsed
        assert repo.update_status.await_count == 1
        repo.update_status.assert_awaited_with("t1", "art_test123", ArtifactStatus.PARSED)
        blob.download_blob.assert_awaited_once()
        publisher.publish_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_permanent_error_when_blob_path_missing(self):
        """Artifact with no blob_path should raise PermanentError."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(
            return_value=_make_artifact(blob_path=None)
        )
        repo.update_status = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.PARSING, blob_path=None)
        )
        handler, _, _, _, _ = _make_handler(repo=repo)

        with pytest.raises(PermanentError, match="no blob path"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_permanent_error_when_artifact_type_missing(self):
        """Artifact with no artifact_type should raise PermanentError."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(
            return_value=_make_artifact(artifact_type=None)
        )
        repo.update_status = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.PARSING, artifact_type=None)
        )
        handler, _, _, _, _ = _make_handler(repo=repo)

        with pytest.raises(PermanentError, match="no artifact type"):
            await handler.handle(_make_event_data())


class TestParserHandleFailure:
    """Tests for the parser failure handler."""

    @pytest.mark.asyncio
    async def test_transitions_to_parse_failed(self):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=_make_artifact(status=ArtifactStatus.PARSING))
        repo.update_status = AsyncMock(return_value=_make_artifact(status=ArtifactStatus.PARSE_FAILED))
        publisher = AsyncMock()

        handler, _, _, _, _ = _make_handler(repo=repo, publisher=publisher)

        await handler.handle_failure(_make_event_data(), PermanentError("bad data"))

        repo.update_status.assert_awaited_once_with("t1", "art_test123", ArtifactStatus.PARSE_FAILED)
        publisher.publish_event.assert_awaited_once()
        published_event = publisher.publish_event.call_args.args[0]
        assert published_event.type == "com.integration-copilot.artifact.parse-failed.v1"

    @pytest.mark.asyncio
    async def test_skips_transition_if_already_past_parse(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(return_value=_make_artifact(status=ArtifactStatus.PARSED))

        await handler.handle_failure(_make_event_data(), PermanentError("bad data"))
        repo.update_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_raise_on_internal_error(self):
        handler, repo, *_ = _make_handler()
        repo.get_by_id = AsyncMock(side_effect=RuntimeError("db down"))

        # Should not raise
        await handler.handle_failure(_make_event_data(), PermanentError("bad data"))

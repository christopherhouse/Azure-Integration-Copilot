"""Tests for the graph builder worker handler (end-to-end with mocks)."""

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
    from domains.projects.models import Project
    from workers.base import PermanentError, TransientError
    from workers.graph_builder.handler import GraphBuilderHandler


def _make_artifact(
    artifact_id: str = "art_test123",
    tenant_id: str = "t1",
    project_id: str = "p1",
    status: ArtifactStatus = ArtifactStatus.PARSED,
) -> Artifact:
    now = datetime.now(UTC)
    return Artifact(
        id=artifact_id,
        partitionKey=tenant_id,
        tenantId=tenant_id,
        projectId=project_id,
        name="test-workflow.json",
        artifactType="logic_app_workflow",
        status=status,
        createdAt=now,
        updatedAt=now,
    )


def _make_project(
    project_id: str = "p1",
    tenant_id: str = "t1",
    graph_version: int = 0,
) -> Project:
    now = datetime.now(UTC)
    return Project(
        id=project_id,
        partitionKey=tenant_id,
        tenantId=tenant_id,
        name="Test Project",
        graphVersion=graph_version,
        createdBy="user1",
        createdAt=now,
        updatedAt=now,
    )


def _make_parse_result() -> dict:
    """Build a mock parse result document."""
    return {
        "id": "pr_test123",
        "partitionKey": "t1",
        "type": "parse_result",
        "tenantId": "t1",
        "projectId": "p1",
        "artifactId": "art_test123",
        "artifactType": "logic_app_workflow",
        "components": [
            {
                "tempId": "tmp_wf1",
                "componentType": "logic_app_workflow",
                "name": "order-processor",
                "displayName": "Order Processor",
                "properties": {"triggerType": "http"},
            },
            {
                "tempId": "tmp_act1",
                "componentType": "logic_app_action",
                "name": "send-email",
                "displayName": "Send Email Action",
                "properties": {"actionType": "Http"},
            },
        ],
        "edges": [
            {
                "sourceTempId": "tmp_wf1",
                "targetTempId": "tmp_act1",
                "edgeType": "calls",
                "properties": None,
            },
        ],
        "externalReferences": [
            {
                "tempId": "tmp_ext1",
                "componentType": "external_service",
                "name": "api.example.com",
                "displayName": "api.example.com",
                "inferredFrom": "https://api.example.com/data",
            },
        ],
        "parsedAt": datetime.now(UTC).isoformat(),
    }


def _make_event_data(
    tenant_id: str = "t1",
    project_id: str = "p1",
    artifact_id: str = "art_test123",
    parse_result_id: str = "pr_test123",
) -> dict:
    return {
        "tenantId": tenant_id,
        "projectId": project_id,
        "artifactId": artifact_id,
        "parseResultId": parse_result_id,
    }


def _make_handler(
    artifact_repo=None,
    graph_repo=None,
    project_repo=None,
    cosmos=None,
    publisher=None,
    parse_result=None,
    project=None,
):
    if artifact_repo is None:
        artifact_repo = AsyncMock()
        artifact_repo.get_by_id = AsyncMock(return_value=_make_artifact())
        artifact_repo.update_status = AsyncMock(
            side_effect=[
                _make_artifact(status=ArtifactStatus.GRAPH_BUILDING),
                _make_artifact(status=ArtifactStatus.GRAPH_BUILT),
            ]
        )
        artifact_repo.update = AsyncMock()

    if graph_repo is None:
        graph_repo = AsyncMock()
        graph_repo.upsert_component = AsyncMock(return_value={})
        graph_repo.upsert_edge = AsyncMock(return_value={})
        graph_repo.upsert_summary = AsyncMock(return_value={})
        graph_repo.compute_summary_counts = AsyncMock(
            return_value={
                "componentCounts": {"logic_app_workflow": 1, "logic_app_action": 1, "external_service": 1},
                "edgeCounts": {"calls": 1},
                "totalComponents": 3,
                "totalEdges": 1,
            }
        )

    if project_repo is None:
        project_repo = AsyncMock()
        project_repo.get_by_id = AsyncMock(return_value=project or _make_project())
        project_repo.update = AsyncMock(return_value=project or _make_project(graph_version=1))

    if cosmos is None:
        cosmos = AsyncMock()
        mock_container = AsyncMock()
        result = parse_result or _make_parse_result()
        mock_container.read_item = AsyncMock(return_value=result)
        cosmos.get_container = AsyncMock(return_value=mock_container)

    if publisher is None:
        publisher = AsyncMock()

    handler = GraphBuilderHandler(
        artifact_repository=artifact_repo,
        graph_repository=graph_repo,
        project_repository=project_repo,
        cosmos_service=cosmos,
        event_publisher=publisher,
    )
    return handler, artifact_repo, graph_repo, project_repo, cosmos, publisher


class TestGraphBuilderIsAlreadyProcessed:
    """Tests for the idempotency check."""

    @pytest.mark.asyncio
    async def test_returns_false_when_artifact_not_found(self):
        handler, artifact_repo, *_ = _make_handler()
        artifact_repo.get_by_id = AsyncMock(return_value=None)
        result = await handler.is_already_processed(_make_event_data())
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_status_is_parsed(self):
        handler, artifact_repo, *_ = _make_handler()
        artifact_repo.get_by_id = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.PARSED)
        )
        result = await handler.is_already_processed(_make_event_data())
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_status_is_graph_building(self):
        handler, artifact_repo, *_ = _make_handler()
        artifact_repo.get_by_id = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.GRAPH_BUILDING)
        )
        result = await handler.is_already_processed(_make_event_data())
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_status_is_graph_built(self):
        handler, artifact_repo, *_ = _make_handler()
        artifact_repo.get_by_id = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.GRAPH_BUILT)
        )
        result = await handler.is_already_processed(_make_event_data())
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_status_is_graph_failed(self):
        handler, artifact_repo, *_ = _make_handler()
        artifact_repo.get_by_id = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.GRAPH_FAILED)
        )
        result = await handler.is_already_processed(_make_event_data())
        assert result is True


class TestGraphBuilderHandle:
    """Tests for the graph builder handler ``handle`` method."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        handler, artifact_repo, graph_repo, project_repo, cosmos, publisher = _make_handler()
        await handler.handle(_make_event_data())

        # Two status transitions: parsed→graph_building, graph_building→graph_built
        assert artifact_repo.update_status.await_count == 2
        calls = artifact_repo.update_status.await_args_list
        assert calls[0].args == ("t1", "art_test123", ArtifactStatus.GRAPH_BUILDING)
        assert calls[1].args == ("t1", "art_test123", ArtifactStatus.GRAPH_BUILT)

        # Components upserted: 2 from components + 1 from externalReferences = 3
        assert graph_repo.upsert_component.await_count == 3

        # Edges upserted: 1
        assert graph_repo.upsert_edge.await_count == 1

        # Summary upserted
        graph_repo.upsert_summary.assert_awaited_once()
        summary_doc = graph_repo.upsert_summary.call_args.args[0]
        assert summary_doc["type"] == "graph_summary"
        assert summary_doc["totalComponents"] == 3
        assert summary_doc["totalEdges"] == 1

        # Project graphVersion incremented
        project_repo.update.assert_awaited_once()

        # Event published
        publisher.publish_event.assert_awaited_once()
        published_event = publisher.publish_event.call_args.args[0]
        assert published_event.type == "com.integration-copilot.graph.updated.v1"
        assert published_event.data["graphVersion"] == 1

    @pytest.mark.asyncio
    async def test_deterministic_ids_for_components(self):
        handler, _, graph_repo, *_ = _make_handler()
        await handler.handle(_make_event_data())

        # Collect component IDs from upsert calls
        component_ids = set()
        for call in graph_repo.upsert_component.call_args_list:
            doc = call.args[0]
            component_ids.add(doc["id"])

        # All IDs should start with "cmp_"
        assert all(cid.startswith("cmp_") for cid in component_ids)

        # Run again — should produce same IDs (deterministic)
        graph_repo.upsert_component.reset_mock()
        handler2, _, graph_repo2, *_ = _make_handler(graph_repo=graph_repo)
        await handler2.handle(_make_event_data())

        component_ids_2 = set()
        for call in graph_repo.upsert_component.call_args_list:
            doc = call.args[0]
            component_ids_2.add(doc["id"])

        assert component_ids == component_ids_2

    @pytest.mark.asyncio
    async def test_edge_resolves_temp_ids_to_stable_ids(self):
        handler, _, graph_repo, *_ = _make_handler()
        await handler.handle(_make_event_data())

        # Verify edge was upserted with stable IDs (not temp IDs)
        edge_doc = graph_repo.upsert_edge.call_args.args[0]
        assert edge_doc["sourceComponentId"].startswith("cmp_")
        assert edge_doc["targetComponentId"].startswith("cmp_")
        assert edge_doc["id"].startswith("edg_")

    @pytest.mark.asyncio
    async def test_graph_version_increments(self):
        project = _make_project(graph_version=5)
        handler, _, graph_repo, project_repo, *_ = _make_handler(project=project)
        await handler.handle(_make_event_data())

        # Project should be updated with version 6
        updated_project = project_repo.update.call_args.args[0]
        assert updated_project.graph_version == 6

        # Summary should have version 6
        summary_doc = graph_repo.upsert_summary.call_args.args[0]
        assert summary_doc["graphVersion"] == 6

    @pytest.mark.asyncio
    async def test_raises_permanent_error_when_parse_result_not_found(self):
        cosmos = AsyncMock()
        mock_container = AsyncMock()
        mock_container.read_item = AsyncMock(side_effect=Exception("not found"))
        # Return empty async iterator for query_items
        mock_container.query_items = MagicMock(return_value=_empty_async_iter())
        cosmos.get_container = AsyncMock(return_value=mock_container)

        handler, *_ = _make_handler(cosmos=cosmos)

        with pytest.raises(PermanentError, match="Parse result not found"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_status_transition_failure(self):
        artifact_repo = AsyncMock()
        artifact_repo.update_status = AsyncMock(
            side_effect=RuntimeError("cosmos timeout")
        )
        handler, *_ = _make_handler(artifact_repo=artifact_repo)

        with pytest.raises(TransientError, match="transition to graph_building"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_permanent_error_when_project_not_found(self):
        project_repo = AsyncMock()
        project_repo.get_by_id = AsyncMock(return_value=None)

        handler, *_ = _make_handler(project_repo=project_repo)

        with pytest.raises(PermanentError, match="Project.*not found"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_component_upsert_failure(self):
        graph_repo = AsyncMock()
        graph_repo.upsert_component = AsyncMock(side_effect=RuntimeError("cosmos error"))
        graph_repo.compute_summary_counts = AsyncMock(return_value={
            "componentCounts": {},
            "edgeCounts": {},
            "totalComponents": 0,
            "totalEdges": 0,
        })

        handler, *_ = _make_handler(graph_repo=graph_repo)

        with pytest.raises(TransientError, match="upsert component"):
            await handler.handle(_make_event_data())


class TestGraphBuilderHandleFailure:
    """Tests for the graph builder failure handler."""

    @pytest.mark.asyncio
    async def test_transitions_to_graph_failed(self):
        artifact_repo = AsyncMock()
        artifact_repo.get_by_id = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.GRAPH_BUILDING)
        )
        artifact_repo.update_status = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.GRAPH_FAILED)
        )
        publisher = AsyncMock()

        handler, *_ = _make_handler(artifact_repo=artifact_repo, publisher=publisher)
        await handler.handle_failure(_make_event_data(), PermanentError("bad data"))

        artifact_repo.update_status.assert_awaited_once_with(
            "t1", "art_test123", ArtifactStatus.GRAPH_FAILED
        )
        publisher.publish_event.assert_awaited_once()
        published_event = publisher.publish_event.call_args.args[0]
        assert published_event.type == "com.integration-copilot.graph.build-failed.v1"

    @pytest.mark.asyncio
    async def test_skips_transition_if_already_graph_built(self):
        artifact_repo = AsyncMock()
        artifact_repo.get_by_id = AsyncMock(
            return_value=_make_artifact(status=ArtifactStatus.GRAPH_BUILT)
        )
        handler, *_ = _make_handler(artifact_repo=artifact_repo)

        await handler.handle_failure(_make_event_data(), PermanentError("bad data"))
        artifact_repo.update_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_raise_on_internal_error(self):
        artifact_repo = AsyncMock()
        artifact_repo.get_by_id = AsyncMock(side_effect=RuntimeError("db down"))
        handler, *_ = _make_handler(artifact_repo=artifact_repo)

        # Should not raise
        await handler.handle_failure(_make_event_data(), PermanentError("bad data"))


class _EmptyAsyncIter:
    """Helper async iterator that yields nothing."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


def _empty_async_iter():
    return _EmptyAsyncIter()

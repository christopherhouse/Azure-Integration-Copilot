"""Parser worker handler — downloads artifacts, parses them, stores results."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from ulid import ULID

from domains.artifacts.models import ArtifactError, ArtifactStatus
from domains.artifacts.repository import ArtifactRepository
from shared.blob import BlobService
from shared.cosmos import CosmosService
from shared.event_types import EVENT_ARTIFACT_PARSE_FAILED, EVENT_ARTIFACT_PARSED
from shared.events import EventGridPublisher, build_cloud_event
from workers.base import PermanentError, TransientError, WorkerHandler
from workers.parser.parsers import UnsupportedArtifactType, get_parser

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DATABASE_NAME = "integration-copilot"
CONTAINER_NAME = "projects"

# Statuses that indicate the artifact has already progressed past the parse stage.
_POST_PARSE_STATUSES: frozenset[ArtifactStatus] = frozenset(
    {
        ArtifactStatus.PARSED,
        ArtifactStatus.PARSE_FAILED,
        ArtifactStatus.GRAPH_BUILDING,
        ArtifactStatus.GRAPH_BUILT,
        ArtifactStatus.GRAPH_FAILED,
    }
)


class ParserHandler(WorkerHandler):
    """Process ``ArtifactScanPassed`` events by parsing the raw artifact
    and storing a structured parse result in Cosmos DB.
    """

    def __init__(
        self,
        artifact_repository: ArtifactRepository,
        blob_service: BlobService,
        cosmos_service: CosmosService,
        event_publisher: EventGridPublisher,
    ) -> None:
        self._repo = artifact_repository
        self._blob = blob_service
        self._cosmos = cosmos_service
        self._publisher = event_publisher

    # -- WorkerHandler interface ----------------------------------------------

    async def is_already_processed(self, event_data: dict[str, Any]) -> bool:
        """Return ``True`` if the artifact has already been parsed or moved past parsing."""
        tenant_id = event_data["tenantId"]
        artifact_id = event_data["artifactId"]

        artifact = await self._repo.get_by_id(tenant_id, artifact_id)
        if artifact is None:
            return False

        return artifact.status in _POST_PARSE_STATUSES

    async def handle(self, event_data: dict[str, Any]) -> None:
        """Parse the artifact: scan_passed → parsing → parsed."""
        tenant_id = event_data["tenantId"]
        project_id = event_data["projectId"]
        artifact_id = event_data["artifactId"]

        log = logger.bind(tenant_id=tenant_id, artifact_id=artifact_id)

        # Fetch artifact and transition scan_passed → parsing.
        # If the artifact is already in PARSING (retry after a transient failure),
        # skip the status transition and continue with the parse attempt.
        try:
            artifact = await self._repo.get_by_id(tenant_id, artifact_id)
        except Exception as exc:
            raise TransientError(f"Failed to fetch artifact: {exc}") from exc

        if artifact is None:
            raise PermanentError(f"Artifact {artifact_id} not found for tenant {tenant_id}")

        if artifact.status != ArtifactStatus.PARSING:
            try:
                artifact = await self._repo.update_status(tenant_id, artifact_id, ArtifactStatus.PARSING)
            except Exception as exc:
                raise TransientError(f"Failed to transition to parsing: {exc}") from exc

            if artifact is None:
                raise PermanentError(f"Artifact {artifact_id} not found for tenant {tenant_id}")

        # Use artifact record as source of truth for blob_path and artifact_type,
        # since upstream events may not include these fields.
        blob_path = artifact.blob_path
        artifact_type = artifact.artifact_type

        if not blob_path:
            raise PermanentError(f"Artifact {artifact_id} has no blob path")

        if not artifact_type:
            raise PermanentError(f"Artifact {artifact_id} has no artifact type")

        log = log.bind(artifact_type=artifact_type)

        # Download raw artifact from Blob Storage
        try:
            content = await self._blob.download_blob(blob_path)
        except Exception as exc:
            raise TransientError(f"Failed to download blob {blob_path}: {exc}") from exc

        # Select parser and parse
        try:
            parser = get_parser(artifact_type)
        except UnsupportedArtifactType as exc:
            raise PermanentError(str(exc)) from exc

        filename = blob_path.rsplit("/", 1)[-1] if "/" in blob_path else blob_path
        try:
            result = parser.parse(content, filename)
        except (ValueError, KeyError, TypeError) as exc:
            raise PermanentError(f"Parse error for {filename}: {exc}") from exc

        result.artifact_id = artifact_id
        result.artifact_type = artifact_type

        # Store parse result in Cosmos DB
        parse_result_id = f"pr_{ULID()}"
        try:
            container = await self._cosmos.get_container(DATABASE_NAME, CONTAINER_NAME)
            doc = {
                "id": parse_result_id,
                "partitionKey": tenant_id,
                "type": "parse_result",
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "artifactType": artifact_type,
                "components": [c.model_dump(by_alias=True, mode="json") for c in result.components],
                "edges": [e.model_dump(by_alias=True, mode="json") for e in result.edges],
                "externalReferences": [r.model_dump(by_alias=True, mode="json") for r in result.external_references],
                "parsedAt": result.parsed_at.isoformat(),
            }
            await container.create_item(body=doc)
        except Exception as exc:
            raise TransientError(f"Failed to store parse result: {exc}") from exc

        # parsing → parsed
        try:
            await self._repo.update_status(tenant_id, artifact_id, ArtifactStatus.PARSED)
        except Exception as exc:
            raise TransientError(f"Failed to transition to parsed: {exc}") from exc

        # Publish ArtifactParsed event
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_PARSED,
            source="/integration-copilot/worker/artifact-parser",
            subject=f"tenants/{tenant_id}/projects/{project_id}/artifacts/{artifact_id}",
            data={
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "parseResultId": parse_result_id,
                "componentCount": len(result.components),
                "edgeCount": len(result.edges),
                "parsedAt": result.parsed_at.isoformat(),
            },
        )
        await self._publisher.publish_event(event)
        log.info("artifact_parsed_event_published", parse_result_id=parse_result_id)

    async def handle_failure(self, event_data: dict[str, Any], error: Exception) -> None:
        """Transition artifact to ``parse_failed`` on permanent error."""
        tenant_id = event_data["tenantId"]
        artifact_id = event_data["artifactId"]

        try:
            artifact = await self._repo.get_by_id(tenant_id, artifact_id)
            if artifact is not None and artifact.status not in _POST_PARSE_STATUSES:
                try:
                    await self._repo.update_status(tenant_id, artifact_id, ArtifactStatus.PARSE_FAILED)
                except Exception:
                    artifact.error = ArtifactError(
                        code="PARSE_FAILED",
                        message=str(error),
                        occurredAt=datetime.now(UTC),
                    )
                    await self._repo.update(artifact)

            # Publish ArtifactParseFailed event
            event = build_cloud_event(
                event_type=EVENT_ARTIFACT_PARSE_FAILED,
                source="/integration-copilot/worker/artifact-parser",
                subject=(
                    f"tenants/{tenant_id}/projects/{event_data.get('projectId', 'unknown')}"
                    f"/artifacts/{artifact_id}"
                ),
                data={
                    "tenantId": tenant_id,
                    "projectId": event_data.get("projectId"),
                    "artifactId": artifact_id,
                    "error": str(error),
                },
            )
            await self._publisher.publish_event(event)
        except Exception:
            logger.error("handle_failure_error", artifact_id=artifact_id, exc_info=True)

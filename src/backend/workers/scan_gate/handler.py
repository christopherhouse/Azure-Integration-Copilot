"""Scan-gate worker handler — transitions artifacts through the malware scan stage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from domains.artifacts.models import ArtifactError, ArtifactStatus
from domains.artifacts.repository import ArtifactRepository
from shared.event_types import EVENT_ARTIFACT_SCAN_FAILED, EVENT_ARTIFACT_SCAN_PASSED
from shared.events import EventGridPublisher, build_cloud_event
from workers.base import PermanentError, TransientError, WorkerHandler

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Statuses that indicate the artifact has already progressed past the scan stage.
_POST_SCAN_STATUSES: frozenset[ArtifactStatus] = frozenset(
    {
        ArtifactStatus.SCAN_PASSED,
        ArtifactStatus.SCAN_FAILED,
        ArtifactStatus.PARSING,
        ArtifactStatus.PARSED,
        ArtifactStatus.PARSE_FAILED,
        ArtifactStatus.GRAPH_BUILDING,
        ArtifactStatus.GRAPH_BUILT,
        ArtifactStatus.GRAPH_FAILED,
    }
)


class ScanGateHandler(WorkerHandler):
    """Process ``ArtifactUploaded`` events by transitioning the artifact
    through the malware-scan stage.

    For the MVP the actual scan is a *passthrough* — the artifact is
    immediately marked ``scan_passed``.  When ``defender_enabled`` is
    ``True`` the handler will integrate with Microsoft Defender for
    Storage (not yet implemented).
    """

    def __init__(
        self,
        artifact_repository: ArtifactRepository,
        event_publisher: EventGridPublisher,
        *,
        defender_enabled: bool = False,
    ) -> None:
        self._repo = artifact_repository
        self._publisher = event_publisher
        self._defender_enabled = defender_enabled

    # -- WorkerHandler interface ----------------------------------------------

    async def is_already_processed(self, event_data: dict[str, Any]) -> bool:
        """Return ``True`` if the artifact has already been scanned or moved past scanning."""
        tenant_id = event_data["tenantId"]
        artifact_id = event_data["artifactId"]

        artifact = await self._repo.get_by_id(tenant_id, artifact_id)
        if artifact is None:
            return False

        return artifact.status in _POST_SCAN_STATUSES

    async def handle(self, event_data: dict[str, Any]) -> None:
        """Transition artifact from ``uploaded`` → ``scanning`` → ``scan_passed``."""
        tenant_id = event_data["tenantId"]
        artifact_id = event_data["artifactId"]
        project_id = event_data["projectId"]

        log = logger.bind(tenant_id=tenant_id, artifact_id=artifact_id)

        # uploaded → scanning
        try:
            artifact = await self._repo.update_status(tenant_id, artifact_id, ArtifactStatus.SCANNING)
        except Exception as exc:
            raise TransientError(f"Failed to transition to scanning: {exc}") from exc

        if artifact is None:
            raise PermanentError(f"Artifact {artifact_id} not found for tenant {tenant_id}")

        # MVP passthrough — skip actual Defender scan
        if self._defender_enabled:
            log.info("defender_scan_not_implemented")

        # scanning → scan_passed
        try:
            await self._repo.update_status(tenant_id, artifact_id, ArtifactStatus.SCAN_PASSED)
        except Exception as exc:
            raise TransientError(f"Failed to transition to scan_passed: {exc}") from exc

        # Publish ArtifactScanPassed event
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_SCAN_PASSED,
            source="/integration-copilot/worker/scan-gate",
            subject=f"tenants/{tenant_id}/projects/{project_id}/artifacts/{artifact_id}",
            data={
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "artifactType": artifact.artifact_type,
                "blobPath": artifact.blob_path,
            },
        )
        await self._publisher.publish_event(event)
        log.info("scan_passed_event_published")

    async def handle_failure(self, event_data: dict[str, Any], error: Exception) -> None:
        """Transition artifact to ``scan_failed`` on permanent error."""
        tenant_id = event_data["tenantId"]
        artifact_id = event_data["artifactId"]

        try:
            artifact = await self._repo.get_by_id(tenant_id, artifact_id)
            if artifact is not None and artifact.status not in _POST_SCAN_STATUSES:
                # Try to move to scan_failed — may fail if status doesn't allow it
                try:
                    await self._repo.update_status(tenant_id, artifact_id, ArtifactStatus.SCAN_FAILED)
                except Exception:
                    # If the status transition is invalid, update error info directly
                    artifact.error = ArtifactError(
                        code="SCAN_FAILED",
                        message=str(error),
                        occurredAt=datetime.now(UTC),
                    )
                    await self._repo.update(artifact)

            # Publish ArtifactScanFailed event
            event = build_cloud_event(
                event_type=EVENT_ARTIFACT_SCAN_FAILED,
                source="/integration-copilot/worker/scan-gate",
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

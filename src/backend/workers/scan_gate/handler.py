"""Scan-gate worker handler — real ClamAV malware scanning via clamd sidecar."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from domains.artifacts.models import ArtifactError, ArtifactStatus, ScanResult
from domains.artifacts.repository import ArtifactRepository
from shared.blob import BlobService
from shared.clamav import ClamAVScanner
from shared.event_types import (
    EVENT_ARTIFACT_SCAN_FAILED,
    EVENT_ARTIFACT_SCAN_PASSED,
    EVENT_ARTIFACT_UPLOADED,
)
from shared.events import EventGridPublisher, build_cloud_event
from workers.base import PermanentError, TransientError, WorkerHandler

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Statuses that indicate the artifact has already progressed past the scan stage.
_POST_SCAN_STATUSES: frozenset[ArtifactStatus] = frozenset(
    {
        ArtifactStatus.SCAN_PASSED,
        ArtifactStatus.SCAN_FAILED,
        ArtifactStatus.QUARANTINED,
        ArtifactStatus.PARSING,
        ArtifactStatus.PARSED,
        ArtifactStatus.PARSE_FAILED,
        ArtifactStatus.GRAPH_BUILDING,
        ArtifactStatus.GRAPH_BUILT,
        ArtifactStatus.GRAPH_FAILED,
    }
)


def _quarantine_blob_path(original_blob_path: str) -> str:
    """Convert an artifact blob path to its quarantine location.

    Original:    tenants/{tenantId}/projects/{projectId}/artifacts/{artifactId}/{filename}
    Quarantined: tenants/{tenantId}/artifacts/quarantine/{projectId}/{artifactId}/{filename}
    """
    parts = original_blob_path.split("/")
    # Expected: ["tenants", tenantId, "projects", projectId, "artifacts", artifactId, filename]
    if len(parts) >= 7 and parts[0] == "tenants" and parts[2] == "projects":
        tenant_id = parts[1]
        project_id = parts[3]
        # Everything after "artifacts/" (artifactId/filename...)
        remainder = "/".join(parts[5:])
        return f"tenants/{tenant_id}/artifacts/quarantine/{project_id}/{remainder}"
    # Fallback: prefix with quarantine
    return f"quarantine/{original_blob_path}"


class ScanGateHandler(WorkerHandler):
    """Process ``ArtifactUploaded`` events by scanning artifact content
    with ClamAV and transitioning through the malware-scan stage.

    Clean artifacts proceed to parsing.  Infected artifacts are
    quarantined — their blob is moved to a quarantine path and the
    artifact status is set to ``quarantined``.
    """

    @property
    def accepted_event_types(self) -> frozenset[str]:
        return frozenset({EVENT_ARTIFACT_UPLOADED})

    def __init__(
        self,
        artifact_repository: ArtifactRepository,
        event_publisher: EventGridPublisher,
        blob_service: BlobService,
        clamav_scanner: ClamAVScanner,
    ) -> None:
        self._repo = artifact_repository
        self._publisher = event_publisher
        self._blob = blob_service
        self._scanner = clamav_scanner

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
        """Scan artifact content and transition based on the result."""
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

        blob_path = artifact.blob_path
        if not blob_path:
            raise PermanentError(f"Artifact {artifact_id} has no blob path")

        # Download blob content for scanning
        try:
            blob_data = await self._blob.download_blob(blob_path)
        except Exception as exc:
            raise TransientError(f"Failed to download blob for scanning: {exc}") from exc

        blob_size = len(blob_data)

        log.info(
            "clamav_scan_starting",
            blob_path=blob_path,
            blob_size_bytes=blob_size,
            artifact_type=artifact.artifact_type,
            artifact_status=artifact.status,
        )

        # Scan with ClamAV
        try:
            scan_result = await self._scanner.scan(blob_data)
        except Exception as exc:
            log.error(
                "clamav_scan_error",
                blob_path=blob_path,
                blob_size_bytes=blob_size,
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            raise TransientError(f"ClamAV scan failed: {exc}") from exc

        scanned_at = datetime.now(UTC)

        log.info(
            "clamav_scan_completed",
            blob_path=blob_path,
            blob_size_bytes=blob_size,
            is_clean=scan_result.is_clean,
            signature=scan_result.signature,
            raw_response=scan_result.raw_response,
        )

        # Write scan metadata to blob
        try:
            await self._blob.set_blob_metadata(blob_path, {
                "scan_status": "clean" if scan_result.is_clean else "infected",
                "scan_signature": scan_result.signature or "",
                "scan_timestamp": scanned_at.isoformat(),
                "scan_scanner": "clamav",
            })
        except Exception:
            log.warning("failed_to_set_blob_scan_metadata", exc_info=True)

        if scan_result.is_clean:
            await self._handle_clean(tenant_id, artifact_id, project_id, artifact, scanned_at, log)
        else:
            await self._handle_malware(
                tenant_id, artifact_id, project_id, artifact, scan_result, scanned_at, log,
            )

    async def _handle_clean(
        self,
        tenant_id: str,
        artifact_id: str,
        project_id: str,
        artifact: Any,
        scanned_at: datetime,
        log: Any,
    ) -> None:
        """Handle a clean scan result — transition to ``scan_passed``."""
        # Transition status via update_status() which validates the state machine
        try:
            updated = await self._repo.update_status(tenant_id, artifact_id, ArtifactStatus.SCAN_PASSED)
        except Exception as exc:
            raise TransientError(f"Failed to transition to scan_passed: {exc}") from exc

        if updated is None:
            raise PermanentError(f"Artifact {artifact_id} not found when transitioning to scan_passed")

        # Persist scan result metadata on the (now scan_passed) artifact
        try:
            updated.scan_result = ScanResult(
                scanner="clamav",
                isClean=True,
                signature=None,
                scannedAt=scanned_at,
            )
            await self._repo.update(updated)
        except Exception:
            log.warning("failed_to_persist_scan_result_metadata", exc_info=True)

        # Publish ArtifactScanPassed event
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_SCAN_PASSED,
            source="/integration-copilot/worker/scan-gate",
            subject=f"tenants/{tenant_id}/projects/{project_id}/artifacts/{artifact_id}",
            data={
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "artifactType": updated.artifact_type,
                "blobPath": updated.blob_path,
            },
        )
        await self._publisher.publish_event(event)
        log.info("scan_passed_event_published")

    async def _handle_malware(
        self,
        tenant_id: str,
        artifact_id: str,
        project_id: str,
        artifact: Any,
        scan_result: Any,
        scanned_at: datetime,
        log: Any,
    ) -> None:
        """Handle a malware detection — quarantine the artifact."""
        log.warning(
            "malware_detected",
            signature=scan_result.signature,
            raw_response=scan_result.raw_response,
        )

        original_blob_path = artifact.blob_path

        # Move blob to quarantine path
        quarantine_path = _quarantine_blob_path(original_blob_path) if original_blob_path else None
        if original_blob_path and quarantine_path:
            try:
                await self._blob.move_blob(original_blob_path, quarantine_path)
            except Exception:
                log.error("failed_to_move_blob_to_quarantine", exc_info=True)
                # Continue with quarantine status even if blob move fails —
                # the artifact is still marked quarantined and hidden from
                # the API.  The blob remains at its original path but is
                # inaccessible to regular consumers.  A future admin cleanup
                # job can reconcile orphaned quarantine blobs.
                quarantine_path = original_blob_path

        # Transition status via update_status() which validates the state machine
        try:
            updated = await self._repo.update_status(tenant_id, artifact_id, ArtifactStatus.QUARANTINED)
        except Exception as exc:
            raise TransientError(f"Failed to transition to quarantined: {exc}") from exc

        if updated is None:
            raise PermanentError(f"Artifact {artifact_id} not found when transitioning to quarantined")

        # Persist scan result, blob path, and error metadata
        try:
            updated.blob_path = quarantine_path
            updated.scan_result = ScanResult(
                scanner="clamav",
                isClean=False,
                signature=scan_result.signature,
                scannedAt=scanned_at,
            )
            updated.error = ArtifactError(
                code="MALWARE_DETECTED",
                message=f"Malware detected: {scan_result.signature or 'unknown signature'}",
                occurredAt=scanned_at,
            )
            await self._repo.update(updated)
        except Exception as exc:
            raise TransientError(f"Failed to update artifact to quarantined: {exc}") from exc

        # Publish ArtifactScanFailed event (NOT scan-passed)
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_SCAN_FAILED,
            source="/integration-copilot/worker/scan-gate",
            subject=f"tenants/{tenant_id}/projects/{project_id}/artifacts/{artifact_id}",
            data={
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "error": f"Malware detected: {scan_result.signature}",
                "quarantined": True,
            },
        )
        await self._publisher.publish_event(event)
        log.info("artifact_quarantined", signature=scan_result.signature)

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

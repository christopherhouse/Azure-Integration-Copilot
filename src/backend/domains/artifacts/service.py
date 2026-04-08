"""Artifact domain service — business logic for artifact metadata."""

import uuid

import structlog
from fastapi import UploadFile

from domains.graph.repository import graph_repository
from domains.projects.repository import project_repository
from domains.tenants.models import Tenant, TierDefinition
from domains.tenants.repository import tenant_repository
from shared.blob import blob_service
from shared.events import ARTIFACT_UPLOADED, build_cloud_event, event_grid_publisher
from shared.exceptions import NotFoundError, QuotaExceededError

from .content_hash import compute_hash
from .models import Artifact, ArtifactStatus, transition_status
from .repository import artifact_repository
from .type_detector import detect_artifact_type

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ArtifactService:
    """Manages artifact metadata operations."""

    async def upload_artifact(
        self,
        tenant: Tenant,
        tier: TierDefinition,
        project_id: str,
        file: UploadFile,
        artifact_type_override: str | None = None,
    ) -> Artifact:
        """Upload an artifact file, store in Blob Storage, and publish event.

        Returns the created artifact metadata document.
        Raises ValueError for file size violations.
        """
        # --- Streaming file size validation ---
        # Read file in chunks to avoid loading the entire payload into memory
        # before checking the size limit.  This prevents DoS from large uploads
        # that would be rejected anyway.
        max_size = tier.limits.max_file_size_mb * 1024 * 1024
        chunks: list[bytes] = []
        bytes_read = 0
        chunk_size = 256 * 1024  # 256 KiB per chunk

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            bytes_read += len(chunk)
            if bytes_read > max_size:
                raise ValueError(
                    f"File size exceeds maximum {max_size} bytes "
                    f"({tier.limits.max_file_size_mb} MB)."
                )
            chunks.append(chunk)

        content = b"".join(chunks)
        file_size = bytes_read
        await file.seek(0)

        # --- Per-project artifact quota check ---
        project = await project_repository.get_by_id(tenant.id, project_id)
        if project is None:
            raise NotFoundError(
                message="Project not found.",
                detail={"project_id": project_id},
            )
        if project.artifact_count >= tier.limits.max_artifacts_per_project:
            raise QuotaExceededError(
                message="Artifact limit per project exceeded.",
                detail={
                    "limit": "max_artifacts_per_project",
                    "current": project.artifact_count,
                    "max": tier.limits.max_artifacts_per_project,
                },
            )

        # --- Generate artifact ID ---
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"

        # --- Detect artifact type ---
        filename = file.filename or "unknown"
        if artifact_type_override:
            detected_type = artifact_type_override
        else:
            detected_type = await detect_artifact_type(filename, file)

        # --- Create initial metadata (status: uploading) ---
        artifact = Artifact(
            id=artifact_id,
            partitionKey=tenant.id,
            tenantId=tenant.id,
            projectId=project_id,
            name=filename,
            artifactType=detected_type,
            status=ArtifactStatus.UPLOADING,
            fileSizeBytes=file_size,
        )
        artifact = await artifact_repository.create(artifact)

        # --- Upload to Blob Storage ---
        blob_path = f"tenants/{tenant.id}/projects/{project_id}/artifacts/{artifact_id}/{filename}"
        await blob_service.upload_blob(blob_path, content, content_type=file.content_type or "application/octet-stream")

        # --- Compute content hash ---
        content_hash = await compute_hash(file)

        # --- Update metadata to uploaded / unsupported ---
        target_status = ArtifactStatus.UNSUPPORTED if detected_type == "unknown" else ArtifactStatus.UPLOADED
        transition_status(artifact.status, target_status)
        artifact.status = target_status
        artifact.blob_path = blob_path
        artifact.content_hash = content_hash
        artifact = await artifact_repository.update(artifact)

        # --- Increment tenant and project usage ---
        await tenant_repository.increment_usage(tenant.id, "total_artifact_count")
        await project_repository.increment_artifact_count(tenant.id, project_id)

        # --- Publish ArtifactUploaded event ---
        if target_status == ArtifactStatus.UPLOADED:
            event = build_cloud_event(
                event_type=ARTIFACT_UPLOADED,
                subject=f"tenants/{tenant.id}/projects/{project_id}/artifacts/{artifact_id}",
                data={
                    "tenantId": tenant.id,
                    "projectId": project_id,
                    "artifactId": artifact_id,
                    "artifactType": detected_type,
                    "blobPath": blob_path,
                    "fileSizeBytes": file_size,
                    "contentHash": content_hash,
                },
            )
            await event_grid_publisher.publish_event(event)

        return artifact

    async def download_artifact(
        self, tenant_id: str, project_id: str, artifact_id: str
    ) -> tuple[bytes, str] | None:
        """Download artifact file content from Blob Storage.

        Returns (content_bytes, filename) or None if artifact not found.
        """
        artifact = await self.get_artifact(tenant_id, project_id, artifact_id)
        if artifact is None or artifact.blob_path is None:
            return None

        content = await blob_service.download_blob(artifact.blob_path)
        return content, artifact.name

    async def get_artifact(
        self, tenant_id: str, project_id: str, artifact_id: str
    ) -> Artifact | None:
        """Get an artifact by ID, scoped to tenant and project.

        Returns ``None`` for deleted or quarantined artifacts — quarantined
        artifacts must never be surfaced to regular API/UI consumers.
        """
        artifact = await artifact_repository.get_by_id(tenant_id, artifact_id)
        if artifact is None:
            return None
        if artifact.project_id != project_id:
            return None
        if artifact.deleted_at is not None:
            return None
        if artifact.status == ArtifactStatus.QUARANTINED:
            return None
        return artifact

    async def list_artifacts(
        self,
        tenant_id: str,
        project_id: str,
        page: int = 1,
        page_size: int = 20,
        status_filter: ArtifactStatus | None = None,
    ) -> tuple[list[Artifact], int]:
        """List artifacts for a project with pagination and optional status filter."""
        return await artifact_repository.list_by_project(
            tenant_id, project_id, page, page_size, status_filter
        )

    async def delete_artifact(
        self, tenant_id: str, project_id: str, artifact_id: str
    ) -> Artifact | None:
        """Permanently delete an artifact and all associated resources.

        Removes the blob from storage, hard-deletes linked graph documents
        (components, edges), hard-deletes parse result documents, hard-deletes
        the artifact metadata document from Cosmos DB, and decrements usage
        counters.
        """
        artifact = await artifact_repository.get_by_id(tenant_id, artifact_id)
        if artifact is None or artifact.project_id != project_id:
            return None

        # Delete blob from storage (best-effort)
        if artifact.blob_path:
            await blob_service.delete_blob(artifact.blob_path)

        # Delete graph documents linked to this artifact (best-effort)
        partition_key = f"{tenant_id}:{project_id}"
        await graph_repository.delete_by_artifact_id(partition_key, artifact_id)

        # Delete parse result documents linked to this artifact (best-effort)
        try:
            await artifact_repository.delete_parse_results_by_artifact_id(tenant_id, artifact_id)
        except Exception:
            logger.warning(
                "parse_result_cleanup_failed",
                tenant_id=tenant_id,
                artifact_id=artifact_id,
                exc_info=True,
            )

        # Hard-delete the artifact metadata document
        deleted = await artifact_repository.hard_delete(tenant_id, artifact_id)
        if deleted:
            await tenant_repository.increment_usage(tenant_id, "total_artifact_count", amount=-1)
            await project_repository.increment_artifact_count(tenant_id, project_id, amount=-1)
        return artifact

    async def rename_artifact(
        self, tenant_id: str, project_id: str, artifact_id: str, new_name: str
    ) -> Artifact | None:
        """Rename an artifact (update the display label).

        Returns the updated artifact or None if not found.
        """
        artifact = await self.get_artifact(tenant_id, project_id, artifact_id)
        if artifact is None:
            return None
        artifact.name = new_name
        return await artifact_repository.update(artifact)


artifact_service = ArtifactService()

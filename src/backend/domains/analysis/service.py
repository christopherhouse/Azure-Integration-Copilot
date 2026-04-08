"""Analysis domain service — business logic for analyses."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from ulid import ULID

from domains.tenants.repository import tenant_repository
from shared.event_types import EVENT_ANALYSIS_REQUESTED
from shared.events import EventGridPublisher, build_cloud_event

from .models import Analysis, AnalysisStatus
from .repository import AnalysisRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _partition_key(tenant_id: str, project_id: str) -> str:
    return f"{tenant_id}:{project_id}"


class AnalysisService:
    """Manages analysis lifecycle operations."""

    def __init__(
        self,
        repository: AnalysisRepository,
        event_publisher: EventGridPublisher,
    ) -> None:
        self._repo = repository
        self._publisher = event_publisher

    async def create_analysis(
        self,
        tenant_id: str,
        project_id: str,
        prompt: str,
        requested_by: str,
    ) -> Analysis:
        """Create a new analysis and publish an AnalysisRequested event."""
        pk = _partition_key(tenant_id, project_id)
        analysis_id = f"ana_{ULID()}"
        now = datetime.now(UTC)

        analysis = Analysis(
            id=analysis_id,
            partitionKey=pk,
            tenantId=tenant_id,
            projectId=project_id,
            prompt=prompt,
            status=AnalysisStatus.PENDING,
            requestedBy=requested_by,
            createdAt=now,
        )

        await self._repo.create(analysis)

        # Increment daily analysis usage counter
        await tenant_repository.increment_usage(tenant_id, "daily_analysis_count")

        event = build_cloud_event(
            event_type=EVENT_ANALYSIS_REQUESTED,
            source="/integration-copilot/api",
            subject=f"tenants/{tenant_id}/projects/{project_id}/analyses/{analysis_id}",
            data={
                "tenantId": tenant_id,
                "projectId": project_id,
                "analysisId": analysis_id,
                "prompt": prompt,
            },
        )
        await self._publisher.publish_event(event)

        logger.info(
            "analysis_created",
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )
        return analysis

    async def get_analysis(
        self, tenant_id: str, project_id: str, analysis_id: str
    ) -> Analysis | None:
        """Get a single analysis by ID."""
        pk = _partition_key(tenant_id, project_id)
        return await self._repo.get_by_id(pk, analysis_id)

    async def list_analyses(
        self, tenant_id: str, project_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Analysis], int]:
        """List analyses for a project (paginated)."""
        pk = _partition_key(tenant_id, project_id)
        return await self._repo.list_by_project(pk, page, page_size)

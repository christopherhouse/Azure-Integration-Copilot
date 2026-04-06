"""Analysis event handler — processes AnalysisRequested events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from domains.analysis.models import AnalysisStatus
from domains.analysis.repository import AnalysisRepository
from shared.event_types import EVENT_ANALYSIS_COMPLETED, EVENT_ANALYSIS_FAILED
from shared.events import EventGridPublisher, build_cloud_event
from shared.pubsub import PubSubService
from workers.base import PermanentError, TransientError, WorkerHandler

from .agent import AgentOrchestrator
from .tools.scoping import AnalysisContext, analysis_context

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AnalysisHandler(WorkerHandler):
    """Process ``AnalysisRequested`` events by running the agent analysis flow."""

    def __init__(
        self,
        analysis_repository: AnalysisRepository,
        event_publisher: EventGridPublisher,
        pubsub_service: PubSubService,
        agent_orchestrator: AgentOrchestrator,
    ) -> None:
        self._repo = analysis_repository
        self._publisher = event_publisher
        self._pubsub = pubsub_service
        self._orchestrator = agent_orchestrator

    async def is_already_processed(self, event_data: dict[str, Any]) -> bool:
        """Return True if the analysis is already completed or failed."""
        tenant_id = event_data["tenantId"]
        project_id = event_data["projectId"]
        analysis_id = event_data["analysisId"]
        pk = f"{tenant_id}:{project_id}"

        analysis = await self._repo.get_by_id(pk, analysis_id)
        if analysis is None:
            return False

        return analysis.status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED)

    async def handle(self, event_data: dict[str, Any]) -> None:
        """Run the analyst → evaluator flow for an AnalysisRequested event."""
        tenant_id = event_data["tenantId"]
        project_id = event_data["projectId"]
        analysis_id = event_data["analysisId"]
        prompt = event_data["prompt"]
        pk = f"{tenant_id}:{project_id}"

        log = logger.bind(
            tenant_id=tenant_id,
            project_id=project_id,
            analysis_id=analysis_id,
        )

        # Load analysis document
        analysis = await self._repo.get_by_id(pk, analysis_id)
        if analysis is None:
            raise PermanentError(f"Analysis {analysis_id} not found")

        # Transition to in_progress
        analysis.status = AnalysisStatus.IN_PROGRESS
        await self._repo.update(analysis)

        # Set scoping context for tool invocations
        ctx = AnalysisContext(tenant_id=tenant_id, project_id=project_id)
        token = analysis_context.set(ctx)

        try:
            # Run the agent analysis flow
            result = await self._orchestrator.run_analysis(prompt)

            # Update analysis with result
            analysis.status = AnalysisStatus.COMPLETED
            analysis.result = result
            analysis.completed_at = datetime.now(UTC)
            await self._repo.update(analysis)

            # Publish AnalysisCompleted event
            event = build_cloud_event(
                event_type=EVENT_ANALYSIS_COMPLETED,
                source="/integration-copilot/worker/analysis",
                subject=f"tenants/{tenant_id}/projects/{project_id}/analyses/{analysis_id}",
                data={
                    "tenantId": tenant_id,
                    "projectId": project_id,
                    "analysisId": analysis_id,
                    "verdict": result.evaluation.verdict if result.evaluation else "UNKNOWN",
                },
            )
            await self._publisher.publish_event(event)

            log.info(
                "analysis_completed",
                verdict=result.evaluation.verdict if result.evaluation else "UNKNOWN",
                retry_count=result.retry_count,
                tool_calls=len(result.tool_calls),
            )

        except Exception as exc:
            log.error("analysis_failed", exc_info=True)
            raise TransientError(f"Analysis failed: {exc}") from exc
        finally:
            analysis_context.reset(token)

    async def handle_failure(self, event_data: dict[str, Any], error: Exception) -> None:
        """Transition analysis to failed on permanent error."""
        tenant_id = event_data["tenantId"]
        project_id = event_data["projectId"]
        analysis_id = event_data["analysisId"]
        pk = f"{tenant_id}:{project_id}"

        try:
            analysis = await self._repo.get_by_id(pk, analysis_id)
            if analysis is not None:
                analysis.status = AnalysisStatus.FAILED
                analysis.error = str(error)
                analysis.completed_at = datetime.now(UTC)
                await self._repo.update(analysis)

            # Publish AnalysisFailed event
            event = build_cloud_event(
                event_type=EVENT_ANALYSIS_FAILED,
                source="/integration-copilot/worker/analysis",
                subject=f"tenants/{tenant_id}/projects/{project_id}/analyses/{analysis_id}",
                data={
                    "tenantId": tenant_id,
                    "projectId": project_id,
                    "analysisId": analysis_id,
                    "error": str(error),
                },
            )
            await self._publisher.publish_event(event)

        except Exception:
            logger.error("handle_failure_error", analysis_id=analysis_id, exc_info=True)

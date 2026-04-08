"""Notification event handler — sends realtime messages via Web PubSub."""

from __future__ import annotations

from typing import Any

import structlog

from shared.event_types import (
    EVENT_ANALYSIS_COMPLETED,
    EVENT_ANALYSIS_FAILED,
    EVENT_ARTIFACT_PARSE_FAILED,
    EVENT_ARTIFACT_PARSED,
    EVENT_ARTIFACT_SCAN_FAILED,
    EVENT_ARTIFACT_SCAN_PASSED,
    EVENT_GRAPH_BUILD_FAILED,
    EVENT_GRAPH_UPDATED,
)
from shared.pubsub import PubSubService
from workers.base import WorkerHandler

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# Maps CloudEvent types to notification types for the frontend.
NOTIFICATION_MAP: dict[str, str] = {
    EVENT_ARTIFACT_SCAN_PASSED: "artifact.status_changed",
    EVENT_ARTIFACT_SCAN_FAILED: "artifact.status_changed",
    EVENT_ARTIFACT_PARSED: "artifact.status_changed",
    EVENT_ARTIFACT_PARSE_FAILED: "artifact.status_changed",
    EVENT_GRAPH_UPDATED: "graph.updated",
    EVENT_GRAPH_BUILD_FAILED: "graph.build_failed",
    EVENT_ANALYSIS_COMPLETED: "analysis.completed",
    EVENT_ANALYSIS_FAILED: "analysis.failed",
}

# Maps CloudEvent types to a status string for artifact sub-type disambiguation.
STATUS_MAP: dict[str, str] = {
    EVENT_ARTIFACT_PARSED: "parsed",
    EVENT_ARTIFACT_PARSE_FAILED: "parse_failed",
    EVENT_ARTIFACT_SCAN_PASSED: "scan_passed",
    EVENT_ARTIFACT_SCAN_FAILED: "scan_failed",
}


class NotificationHandler(WorkerHandler):
    """Process terminal events and send Web PubSub notifications."""

    @property
    def accepted_event_types(self) -> frozenset[str]:
        return frozenset(NOTIFICATION_MAP.keys())

    def __init__(self, pubsub_service: PubSubService) -> None:
        self._pubsub = pubsub_service

    async def is_already_processed(self, event_data: dict[str, Any]) -> bool:
        """Notifications are idempotent (safe to re-send), so always False."""
        return False

    async def handle(self, event_data: dict[str, Any]) -> None:
        """Send realtime notifications for terminal events."""
        event_type = event_data.get("_event_type", "")
        notification_type = NOTIFICATION_MAP.get(event_type)

        if not notification_type:
            logger.debug("notification_skipped", event_type=event_type)
            return

        tenant_id = event_data.get("tenantId", "")
        project_id = event_data.get("projectId")

        if not tenant_id:
            logger.warning("notification_missing_tenant_id", event_type=event_type)
            return

        payload = {
            "type": notification_type,
            "data": self._build_payload(event_data, event_type),
        }

        # Send to tenant group
        await self._pubsub.send_to_group(
            group=f"tenant:{tenant_id}",
            data=payload,
        )

        # Send to project group if applicable
        if project_id:
            await self._pubsub.send_to_group(
                group=f"project:{tenant_id}:{project_id}",
                data=payload,
            )

        logger.info(
            "notification_sent",
            notification_type=notification_type,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def handle_failure(self, event_data: dict[str, Any], error: Exception) -> None:
        """Log notification failures but don't transition any state."""
        logger.error(
            "notification_delivery_failed",
            event_type=event_data.get("_event_type"),
            error=str(error),
        )

    @staticmethod
    def _build_payload(event_data: dict[str, Any], event_type: str = "") -> dict[str, Any]:
        """Extract a clean payload for the frontend notification."""
        # Pass through relevant fields, excluding internal metadata
        result = {
            k: v
            for k, v in event_data.items()
            if not k.startswith("_") and k != "partitionKey"
        }
        # Inject status for artifact sub-type disambiguation
        status = STATUS_MAP.get(event_type)
        if status:
            result["status"] = status
        return result

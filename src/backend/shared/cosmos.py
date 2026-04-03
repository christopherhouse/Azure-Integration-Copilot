from __future__ import annotations

import threading
from typing import Any

import structlog
from azure.core.pipeline import PipelineRequest, PipelineResponse
from azure.core.pipeline.policies import DistributedTracingPolicy
from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.identity.aio import DefaultAzureCredential

from config import settings
from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# RU-charge enrichment on Cosmos DB dependency spans
# ---------------------------------------------------------------------------

# Guard + lock to ensure the monkey-patch is applied at most once.
_ru_patch_applied = False
_ru_patch_lock = threading.Lock()


def _enrich_span_with_request_charge(
    span: Any,
    response: PipelineResponse,  # type: ignore[type-arg]
) -> None:
    """Set ``db.cosmosdb.request_charge`` on *span* from the response headers.

    The ``x-ms-request-charge`` header is present on every Cosmos DB response
    and contains the Request Unit (RU) cost of the operation.  This mirrors the
    attribute that the .NET and Java Azure Cosmos DB SDKs emit natively but
    that the Python SDK does not yet include.
    """
    try:
        request_charge = response.http_response.headers.get("x-ms-request-charge")
        if request_charge is not None and hasattr(span, "is_recording") and span.is_recording():
            span.set_attribute("db.cosmosdb.request_charge", float(request_charge))
    except Exception:  # noqa: BLE001
        # Telemetry enrichment must never break the request pipeline.
        pass


def _patch_distributed_tracing_for_ru_cost() -> None:
    """Monkey-patch ``DistributedTracingPolicy.on_response`` to capture RU cost.

    In the azure-cosmos pipeline the policy ordering is::

        … → CustomHookPolicy → … → DistributedTracingPolicy → … → Transport

    Because ``CustomHookPolicy`` sits *before* ``DistributedTracingPolicy``,
    its ``on_response`` (which fires ``raw_response_hook``) runs *after*
    ``DistributedTracingPolicy.on_response`` has already ended the span.
    At that point the span is no longer recording and the RU attribute is
    silently dropped.

    This patch wraps ``on_response`` so that the RU header is read and set on
    the span **before** the original method ends it.  The span is retrieved
    from the pipeline request context (``TRACING_CONTEXT``), which is where
    ``DistributedTracingPolicy.on_request`` stores it.

    The patch is idempotent and safe for non-Cosmos pipelines: when the
    ``x-ms-request-charge`` header is absent the wrapper is a no-op.
    """
    global _ru_patch_applied  # noqa: PLW0603
    with _ru_patch_lock:
        if _ru_patch_applied:
            return
        _ru_patch_applied = True

    _original_on_response = DistributedTracingPolicy.on_response

    def _on_response_with_ru(
        self: DistributedTracingPolicy,
        request: PipelineRequest,  # type: ignore[type-arg]
        response: PipelineResponse,  # type: ignore[type-arg]
    ) -> None:
        # Grab the span BEFORE the original on_response ends it.
        try:
            span = request.context.get(self.TRACING_CONTEXT)
            if span is not None:
                _enrich_span_with_request_charge(span, response)
        except Exception:  # noqa: BLE001
            pass
        _original_on_response(self, request, response)

    DistributedTracingPolicy.on_response = _on_response_with_ru  # type: ignore[assignment]


class CosmosService:
    """Async wrapper around Azure Cosmos DB client."""

    def __init__(self) -> None:
        self._client: CosmosClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> CosmosClient:
        if self._client is None:
            _patch_distributed_tracing_for_ru_cost()
            self._credential = create_credential()
            self._client = CosmosClient(
                url=settings.cosmos_db_endpoint,
                credential=self._credential,
            )
        return self._client

    async def get_container(self, database_name: str, container_name: str) -> ContainerProxy:
        """Get a Cosmos DB container client."""
        client = await self._get_client()
        database = client.get_database_client(database_name)
        return database.get_container_client(container_name)

    async def ping(self) -> bool:
        """Check connectivity to Cosmos DB. Returns True if reachable."""
        try:
            client = await self._get_client()
            # List databases as a connectivity check
            async for _ in client.list_databases():
                break
            return True
        except Exception:
            logger.warning("cosmos_ping_failed", exc_info=True)
            return False

    async def close(self) -> None:
        """Close the Cosmos DB client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None


cosmos_service = CosmosService()

"""Tool: get_component_details — returns details for a specific component."""

from __future__ import annotations

import json
from typing import Annotated

import structlog
from pydantic import Field

from domains.graph.repository import graph_repository

from .scoping import analysis_context

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def get_component_details(
    component_id: Annotated[str, Field(description="The component ID to look up.")],
) -> str:
    """Get detailed information about a specific component in the dependency graph.

    Returns the component's type, properties, and tags.
    """
    ctx = analysis_context.get()
    pk = f"{ctx.tenant_id}:{ctx.project_id}"

    component = await graph_repository.get_component(pk, component_id)
    if component is None:
        return json.dumps({"error": f"Component '{component_id}' not found."})

    return json.dumps({
        "id": component.id,
        "name": component.name,
        "displayName": component.display_name,
        "componentType": component.component_type,
        "properties": component.properties,
        "tags": component.tags,
        "artifactId": component.artifact_id,
        "graphVersion": component.graph_version,
    })

"""Tool: get_graph_neighbors — returns neighbors for a component."""

from __future__ import annotations

import json
from typing import Annotated

import structlog
from pydantic import Field

from domains.graph.repository import graph_repository

from .scoping import analysis_context

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def get_graph_neighbors(
    component_id: Annotated[str, Field(description="The component ID to find neighbors for.")],
    direction: Annotated[str, Field(description="Edge direction filter: 'both', 'incoming', or 'outgoing'.")] = "both",
) -> str:
    """Get the neighboring components connected to a given component.

    Returns incoming, outgoing, or both directions.
    """
    ctx = analysis_context.get()
    pk = f"{ctx.tenant_id}:{ctx.project_id}"

    neighbors = await graph_repository.get_neighbors(pk, component_id, direction)

    result = []
    for n in neighbors:
        edge = n["edge"]
        comp = n["component"]
        result.append({
            "direction": n["direction"],
            "edge": {
                "id": edge.id,
                "edgeType": edge.edge_type,
                "sourceComponentId": edge.source_component_id,
                "targetComponentId": edge.target_component_id,
            },
            "component": {
                "id": comp.id,
                "name": comp.name,
                "displayName": comp.display_name,
                "componentType": comp.component_type,
            },
        })

    return json.dumps({"neighbors": result, "count": len(result)})

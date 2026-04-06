"""Tool: run_impact_analysis — BFS traversal for transitive dependencies."""

from __future__ import annotations

import json
from collections import deque
from typing import Annotated

import structlog
from pydantic import Field

from domains.graph.repository import graph_repository

from .scoping import analysis_context

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def run_impact_analysis(
    component_id: Annotated[str, Field(description="The component ID to start traversal from.")],
    direction: Annotated[
        str,
        Field(description="Traversal direction — 'downstream' (outgoing) or 'upstream' (incoming)."),
    ],
    max_depth: Annotated[int, Field(description="Maximum traversal depth (default 3, capped at 5).")] = 3,
) -> str:
    """Perform a breadth-first traversal from a component to find all transitively dependent components.

    Returns the root component, list of impacted components, and total count.
    """
    ctx = analysis_context.get()
    pk = f"{ctx.tenant_id}:{ctx.project_id}"
    max_depth = min(int(max_depth), 5)

    # Map direction to graph neighbor direction
    edge_direction = "outgoing" if direction == "downstream" else "incoming"

    # BFS traversal
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    queue.append((component_id, 0))
    visited.add(component_id)

    impacted: list[dict] = []

    while queue:
        current_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        neighbors = await graph_repository.get_neighbors(pk, current_id, edge_direction)
        for n in neighbors:
            comp = n["component"]
            comp_id = comp.id
            if comp_id not in visited:
                visited.add(comp_id)
                impacted.append({
                    "id": comp_id,
                    "name": comp.name,
                    "displayName": comp.display_name,
                    "componentType": comp.component_type,
                    "depth": depth + 1,
                })
                queue.append((comp_id, depth + 1))

    # Get root component info
    root = await graph_repository.get_component(pk, component_id)
    root_info = {
        "id": component_id,
        "name": root.name if root else component_id,
        "componentType": root.component_type if root else "unknown",
    }

    return json.dumps({
        "rootComponent": root_info,
        "direction": direction,
        "maxDepth": max_depth,
        "impactedComponents": impacted,
        "totalImpacted": len(impacted),
    })

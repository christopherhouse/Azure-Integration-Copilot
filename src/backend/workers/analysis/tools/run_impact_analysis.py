"""Tool: run_impact_analysis — BFS traversal for transitive dependencies."""

from __future__ import annotations

import json
from collections import deque

import structlog
from azure.ai.projects.models import FunctionTool

from domains.graph.repository import graph_repository

from .scoping import analysis_context

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

TOOL_RUN_IMPACT_ANALYSIS = FunctionTool(
    name="run_impact_analysis",
    description=(
        "Perform a breadth-first traversal from a component to find all "
        "transitively dependent components. Returns the root component, "
        "list of impacted components, and total count."
    ),
    parameters={
        "type": "object",
        "properties": {
            "component_id": {
                "type": "string",
                "description": "The component ID to start traversal from.",
            },
            "direction": {
                "type": "string",
                "enum": ["downstream", "upstream"],
                "description": "Traversal direction — 'downstream' (outgoing) or 'upstream' (incoming).",
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum traversal depth (default 3, capped at 5).",
            },
        },
        "required": ["component_id", "direction"],
        "additionalProperties": False,
    },
    strict=False,
)


async def execute_run_impact_analysis(
    component_id: str, direction: str, max_depth: int = 3, **_kwargs: object
) -> str:
    """Execute run_impact_analysis scoped to the current tenant/project."""
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

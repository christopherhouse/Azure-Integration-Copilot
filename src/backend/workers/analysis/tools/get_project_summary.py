"""Tool: get_project_summary — returns graph summary data for the current project."""

from __future__ import annotations

import json

import structlog
from azure.ai.projects.models import FunctionTool

from domains.graph.repository import graph_repository

from .scoping import analysis_context

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

TOOL_GET_PROJECT_SUMMARY = FunctionTool(
    name="get_project_summary",
    description=(
        "Get a summary of the integration project's dependency graph, "
        "including total component and edge counts broken down by type."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
    strict=True,
)


async def execute_get_project_summary(**_kwargs: object) -> str:
    """Execute get_project_summary scoped to the current tenant/project."""
    ctx = analysis_context.get()
    pk = f"{ctx.tenant_id}:{ctx.project_id}"

    summary = await graph_repository.get_summary(pk)
    if summary is None:
        return json.dumps({"error": "No graph data found for this project."})

    return json.dumps({
        "totalComponents": summary.total_components,
        "totalEdges": summary.total_edges,
        "componentCounts": summary.component_counts,
        "edgeCounts": summary.edge_counts,
        "graphVersion": summary.graph_version,
    })

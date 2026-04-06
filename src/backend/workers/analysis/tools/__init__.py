"""Custom tools for the integration-analyst agent."""

from .get_component_details import TOOL_GET_COMPONENT_DETAILS, execute_get_component_details
from .get_graph_neighbors import TOOL_GET_GRAPH_NEIGHBORS, execute_get_graph_neighbors
from .get_project_summary import TOOL_GET_PROJECT_SUMMARY, execute_get_project_summary
from .run_impact_analysis import TOOL_RUN_IMPACT_ANALYSIS, execute_run_impact_analysis

ALL_TOOLS = [
    TOOL_GET_PROJECT_SUMMARY,
    TOOL_GET_GRAPH_NEIGHBORS,
    TOOL_GET_COMPONENT_DETAILS,
    TOOL_RUN_IMPACT_ANALYSIS,
]

TOOL_DISPATCH = {
    "get_project_summary": execute_get_project_summary,
    "get_graph_neighbors": execute_get_graph_neighbors,
    "get_component_details": execute_get_component_details,
    "run_impact_analysis": execute_run_impact_analysis,
}

__all__ = [
    "ALL_TOOLS",
    "TOOL_DISPATCH",
]

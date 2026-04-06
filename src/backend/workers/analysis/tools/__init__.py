"""Custom tools for the integration-analyst agent.

Each tool is a plain async Python function with type annotations.
The Microsoft Agent Framework auto-generates JSON schemas from the
function signatures and docstrings.
"""

from .get_component_details import get_component_details
from .get_graph_neighbors import get_graph_neighbors
from .get_project_summary import get_project_summary
from .run_impact_analysis import run_impact_analysis

ALL_TOOLS = [
    get_project_summary,
    get_graph_neighbors,
    get_component_details,
    run_impact_analysis,
]

__all__ = [
    "ALL_TOOLS",
    "get_project_summary",
    "get_graph_neighbors",
    "get_component_details",
    "run_impact_analysis",
]

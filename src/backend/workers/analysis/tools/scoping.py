"""Tenant/project scoping context for tool invocations.

The analysis worker sets the context before invoking agents.  Tool functions
read the context to enforce tenant/project isolation without exposing
tenant IDs to the agent.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisContext:
    """Immutable context carrying the tenant and project being analysed."""

    tenant_id: str
    project_id: str
    retry_count: int = 0


# Set by the worker before agent invocation, read by tool functions.
analysis_context: contextvars.ContextVar[AnalysisContext] = contextvars.ContextVar(
    "analysis_context"
)

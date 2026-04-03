"""Deterministic ID generation for graph components and edges."""

import hashlib


def generate_component_id(
    tenant_id: str, project_id: str, component_type: str, canonical_name: str
) -> str:
    """Generate a deterministic component ID from its identifying attributes.

    The same inputs always produce the same ID, ensuring that re-uploading
    an artifact updates existing nodes rather than creating duplicates.
    """
    key = f"{tenant_id}:{project_id}:{component_type}:{canonical_name}"
    return f"cmp_{hashlib.sha256(key.encode()).hexdigest()[:20]}"


def generate_edge_id(source_id: str, target_id: str, edge_type: str) -> str:
    """Generate a deterministic edge ID from source, target, and type.

    The same inputs always produce the same ID, preventing duplicate edges.
    """
    key = f"{source_id}:{target_id}:{edge_type}"
    return f"edg_{hashlib.sha256(key.encode()).hexdigest()[:20]}"
